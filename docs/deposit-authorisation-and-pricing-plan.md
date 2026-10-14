# Deposit authorisation and pricing plan

## Decision summary

Rentalution must continue to use **number of rental days** as the customer-facing rule, while enforcing the actual Stripe/card-network expiry returned for the individual authorisation.

Do not introduce one flat payment fee for every rental. It would charge short rentals for a risk and payment cost they do not create. Instead, show and charge a clearly labelled **deposit handling fee only where the selected deposit route has a non-recoverable processing cost**.

The current `7–30 day Visa credit or Mastercard credit` rule is incomplete: it restricts the saved card, but the Stripe PaymentIntent does not request extended authorisation and we do not save Stripe's `capture_before` timestamp. Card brand alone does not create a 30-day hold.

## Why the present seven-day assumption is unsafe

A manual card authorisation must be captured or cancelled before the `capture_before` time returned by Stripe. It is often seven days for online cards, but can be shorter: Stripe documents a 4 day 18 hour Visa merchant-initiated window. Stripe also supports extended authorisations for eligible cards, but availability and time limits vary by card network, merchant category, transaction type, and Stripe pricing plan.

Sources:

- [Stripe: place a hold on a payment method](https://docs.stripe.com/payments/place-a-hold-on-a-payment-method)
- [Stripe: extended authorisations](https://docs.stripe.com/payments/extended-authorization)
- [Stripe UK pricing](https://stripe.com/gb/pricing)

## Proposed rental-day policy

These are the rules presented to customers. The final route is always validated against the real `capture_before` date, with a safety buffer.

| Rental length | Preferred deposit route | Customer cost | Fallback if the hold cannot safely cover the return deadline |
| --- | --- | --- | --- |
| 1–3 days | Standard authorisation hold; release at resolution | No deposit handling fee | Capture/refund only when the card network expiry makes the hold unsafe |
| 4–28 days | Request extended authorisation (`if_available`) on an eligible card | No fee where the extended hold creates no additional Stripe cost | Offer a funded deposit, with its cost shown before confirmation |
| 29+ days | Funded deposit: capture at collection and refund the returned share at settlement | Deposit handling fee shown up front, unless Rentalution absorbs it | No hold option |

### Why 28 days instead of a simple “under 30 days” promise?

Visa's extended window is effectively 29 days 18 hours, not a guaranteed 30 days. Even though the no-response workflow now resolves at **23:30 on the return date**, a 29-day rental may leave too little time for the actual authorisation time and a safety buffer. The system must calculate:

`required settlement deadline = rental_end_date at 23:30 Europe/London`

`hold route allowed = required settlement deadline < capture_before - safety_buffer`

Use a 24-hour safety buffer initially. This makes the advertised bands simple without making an unsafe promise. A booking can still move to funded deposit when Stripe returns an earlier deadline.

## Card-brand and cost rules

The existing Visa-credit/Mastercard-credit restriction should not be treated as proof of a 30-day hold.

- Mastercard extended authorisation can be available for all merchant categories for up to 30 days.
- Visa extended authorisation can be available up to 30 days; for general merchant categories Stripe documents an additional 0.08% cost and says this route applies only to customer-initiated transactions.
- The current deposit collection is confirmed `off_session`, so we must not assume Visa extended authorisation will apply. Request it as `if_available`, inspect the result, and use the returned deadline.
- Extended authorisation requires suitable Stripe account access (Stripe documents it as an IC+ feature, with support contact needed for blended pricing).
- A captured deposit can be refunded later, but Stripe’s standard pricing does not return the original card processing fee. The refund operation itself generally has no additional fee for card payments.

## Customer-facing page/content

Create a **“How your deposit is handled”** page, linked from booking checkout, the card page, and transaction details. It must show the selected route before the renter confirms.

### Suggested copy

> **Your rental deposit**
>
> We protect both people by reserving or collecting the deposit until the item is returned and any return issue is raised.
>
> For short rentals, we normally place a temporary card hold. Your bank may display this as pending; it is released when the rental is resolved.
>
> For longer rentals, card networks may not allow a hold to remain open for the whole rental. In that case we collect the deposit and refund the amount due back to the same card after the return is resolved.
>
> Before you confirm, we show whether your deposit is a temporary hold or a collected deposit, the deposit amount, any deposit-handling fee, and the expected automatic-resolution date.
>
> We presume the item is returned on its agreed return date. At 21:00 that evening, we remind the lender to report any missing return or other problem. If none is reported by 23:30, we return the full deposit and close the booking automatically. Reporting a problem stops automatic resolution.

The checkout breakdown should contain separate rows, never hide this inside the service fee:

| Row | Example |
| --- | --- |
| Rental and delivery | £42.00 |
| Rentalution service fee | £4.20 |
| Deposit | £100.00 — *temporary hold* or *collected and refundable* |
| Deposit handling fee | £0.00 or the disclosed amount |
| Amount charged today | £46.20 or £146.20 plus any disclosed handling fee |

## Fee recommendation

1. Keep the existing Rentalution service fee separate from deposit handling.
2. Do **not** add a universal flat payment fee.
3. For standard/extended holds with no incremental cost, show `Deposit handling fee: £0.00`.
4. For a funded-deposit fallback, calculate and disclose a route-specific handling fee before commitment. Initial policy choice: either absorb it during beta, or recover only the expected unrecoverable Stripe processing cost. Do not mark it up until support, dispute, and refund costs are measured.
5. Store the quoted fee and route on the transaction so changes to pricing later do not alter an already-agreed booking.

## Implementation plan

### Phase 0 — commercial and Stripe validation

1. Confirm Rentalution's Stripe pricing model (standard/blended versus IC+) and merchant category code with Stripe.
2. Confirm which UK Visa and Mastercard payments receive extended authorisation in live mode, and whether Visa's 0.08% applies to our merchant category.
3. Decide whether funded-deposit fallback cost is absorbed during beta or charged to the renter.
4. Agree the initial safety buffer (recommended: 24 hours) and the maximum permitted rental days for each route.

### Phase 1 — data model and pricing engine

1. Add a `deposit_route` enum: `standard_hold`, `extended_hold`, `funded_deposit`.
2. Add immutable quote fields: `deposit_handling_fee`, `deposit_route_quoted_at`, `deposit_capture_before`, `deposit_extended_authorisation_status`, and `deposit_settlement_deadline`.
3. Create one service that derives the provisional route from rental days and computes the local UK settlement deadline. Use it in web, mobile API, admin, and checkout so they cannot drift.
4. Preserve the existing `>30 days` funded-deposit rule until Phase 2 has been live-tested; do not activate a new 28-day rule by template logic alone.

### Phase 2 — Stripe integration

1. For the 4–28-day provisional route, create a manual-capture PaymentIntent with `request_extended_authorization=if_available` and expand `latest_charge`.
2. Read and persist `payment_method_details.card.capture_before` and extended-authorisation status.
3. Compare that expiry to the settlement deadline plus buffer.
4. If safe, retain the hold route. If unsafe/unavailable, cancel the authorisation and obtain explicit confirmation for the funded-deposit route and its displayed cost; do not silently charge it.
5. For the funded route, capture the deposit and refund/award at final settlement. Record original Stripe fee, refund status, and any transfer separately in the ledger.

### Phase 3 — user experience

1. Build the “How your deposit is handled” page using the copy above.
2. Add a checkout route card: `Temporary hold` or `Collected refundable deposit`, with the date/time it will be automatically resolved.
3. Show the route and fee in rental terms, order confirmation, booking details, and email receipt.
4. Show a clear fallback prompt if an extended hold is not available: “Your card cannot support a hold for this rental length. Continue with a refundable collected deposit of £X and handling fee £Y?”

### Phase 4 — workflow automation and safeguards

1. Keep the 21:00 lender reminder and 23:30 UK-time presumed-on-time-return settlement.
2. Add a scheduled expiry guard that checks every unresolved held deposit against its stored `deposit_capture_before` and alerts/escalates before the buffer is breached.
3. Never auto-close a transaction whose fund release/refund fails or remains pending; move it to a staff-visible payment exception state instead.
4. A missing-return report, dispute, or pending evidence must stop automatic resolution.

### Phase 5 — testing, rollout, and monitoring

1. Test all three routes, including Visa/MC success and extended-auth unavailability, DST changes, 28/29/30-day boundaries, refund pending/failure, and duplicate task delivery.
2. Add Stripe test/live-mode verification before enabling the extended-hold route in production.
3. Release behind a feature flag; begin with staff-visible logging and no automatic funded fallback.
4. Monitor expiry-guard incidents, refund completion times, Stripe fee loss, conversion impact, disputes, and user support contacts for 30 days.
5. Only then finalise the per-route fee policy and customer copy.

## Immediate code corrections required

- Keep the current `>30 days` captured-deposit behaviour until the above is implemented.
- Do not rely on the current 7–30-day card restriction as a payment safety control.
- Add a migration and payment service rather than embedding day thresholds in templates.
- Update the existing `transaction_deposit_verification_dispute_flow.md` when the commercial choices are approved, so it no longer describes the incomplete 7–30-day flow as complete.
