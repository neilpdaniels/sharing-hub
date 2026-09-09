# Order Addition, Transaction Flow, and Fees

This document is the working reference for the rental lifecycle. Keep it aligned with the backend rules in `transaction/models.py` and the UI copy in the web and mobile apps.

## Order Addition

This is the listing setup flow a lender uses before any rental exists.

1. The lender creates or edits an order/listing.
2. The lender sets the daily price, deposit, collection or delivery rules, and maximum rental duration.
3. The lender can add price bands for longer bookings.
4. If the lender allows 7 to 30 day rentals, the UI should make the deposit card rule clear.
5. If the lender allows rentals over 30 days, the UI should explain that the full deposit has to be taken and returned later rather than held as a card authorisation, and that fees are higher because of the extra payment handling.
6. The backend validates the listing data and stores the fee and deposit rules for later transaction use.

## Deposit tiers

- `Sub 7 days`: standard deposit handling.
- `7 to 30 days`: the deposit card must be a Visa credit card or Mastercard credit card.
- `Over 30 days`: the full deposit is taken and returned later rather than held as a card authorisation, and the fees are higher because of the extra payment handling.

## Transaction Flow

1. The renter sends an enquiry with dates and a message.
2. The lender reviews the request and agrees or declines.
3. The agreement is confirmed by both sides.
4. The renter sets up the payment card needed for deposit and charges.
5. Checkout: renter uploads video, lender checks code.
6. Return: renter uploads video, lender reviews, renter checks code.
7. The deposit is returned, reduced, or contested.
8. Feedback is exchanged and the transaction closes.

## Mobile action boxes

- Keep the agreement, checkout, return, and deposit actions inside the single `Actions` card on the mobile transaction screen.
- Do not show checkout evidence while the agreement is still awaiting confirmation.
- The checkout section should stay short: `Checkout video`, `Checkout code`, and `Checkout PIN`.
- The return section should stay short: `Return video`, `Return code`, `Return PIN`, and `Return review`.
- The lender return review and counter-evidence controls should stay in the same `Actions` card so it is obvious whether the lender is agreeing or disputing the return.

## Role actions

### Renter

- Confirm the agreement when the lender has agreed.
- Add or review the deposit card when the listing requires it.
- Upload checkout video once the rental has moved into the checkout verification step.
- Upload return video at check-in / return time.
- Use the return code shown in the action box to confirm the item has been returned.
- Agree to, contest, or escalate the deposit return if required.
- Leave feedback when the transaction reaches the closeout stage.

### Lender

- Agree or decline the enquiry.
- Confirm the agreement when it is their turn to sign.
- Review checkout video and use the checkout code shown in the action box to complete handover.
- Review return video and either agree with it or add lender evidence if the return is not complete.
- Share the return code shown in the action box so the renter can confirm the handover.
- Propose, update, or dispute the deposit return.
- Leave feedback when the transaction reaches the closeout stage.

## Transaction Fees

- Delivery charges are passed to the renter.
- The banded Rentalution fee is passed to the renter.
- Any deposit-related card cost that arises from a captured hold is also passed to the renter.
- Fee totals shown in the UI should match the charge records created for the transaction.

## Verification flow

- Stripe identity verification is used where the listing or workflow requires verified users.
- Card setup is separate from identity verification.
- For 7 to 30 day rentals, the deposit card restriction is enforced in the backend and mirrored in the UI.

## Dispute flow

- Condition, missing return, missing rental, and deposit return can all escalate into dispute handling.
- Evidence from checkout and return remains attached to the transaction.
- The dispute team reviews the evidence and issues the final outcome.

## Maintenance notes

- Keep the backend as the source of truth for tiering and card eligibility.
- Update the web and mobile copy whenever the policy wording changes.
- Add or adjust tests whenever the deposit tiers, listing rules, or dispute stages move.
