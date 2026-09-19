# Stripe Connect Settlement TODO

## Goal

Use Stripe Express connected accounts and separate charges/transfers.

- Renter pays rental + delivery + Rentalution service fee.
- Rentalution service fee is 10% of rental + delivery.
- Rentalution holds rental proceeds until verified return handover.
- On successful return, lender receives rental + delivery.
- Full deposit return cancels the authorization; borrower is not charged.
- Partial agreed return or dispute award captures only the lender award.
- Lender receives `max(0, deposit award - actual Stripe processing fee)`.
- Rentalution absorbs only a processing-fee shortfall where the award is smaller than the fee.

## Your Actions: Stripe Owner Runbook

These are the actions that require access to the Rentalution Stripe account. They
are **for you**, not engineering tasks. Complete them in a Stripe Sandbox first; do not
place live credentials in a local environment or source control.

### A. Enable Connect In A Development Sandbox

- [ ] **YOU: Sign in to the [Stripe Dashboard](https://dashboard.stripe.com/) and use the account picker to create or switch to a Sandbox named `Rentalution development`.** Do not use Live mode. Stripe now recommends a Sandbox over its older shared Test mode because it is isolated from other testing and live configuration. See [Stripe's sandbox guide](https://docs.stripe.com/get-started/test-developer-integration).
- [ ] **YOU: Open Connect inside that Sandbox.** Complete Stripe's Connect activation prompts for Rentalution as the platform. Choose **Express** when Stripe asks which connected-account experience to use.
- [ ] **YOU: Record the business decisions Stripe requests for the platform.** Use the real Rentalution legal business name, UK address, support email, support URL, and the marketplace/product description. This is platform information, not lender information.
- [ ] **YOU: In Connect settings inside the Sandbox, set the platform branding shown during hosted lender onboarding.** Add Rentalution's display name, icon/logo, brand colour, support contact details, and privacy/terms URLs once those URLs are live.
- [ ] **YOU: Confirm in Stripe's [supported countries guidance](https://docs.stripe.com/connect/cross-border-payouts) that our intended lender countries, GBP, and UK platform arrangement are supported.** Note any country limitation in the project issue/tracker before we enable that country in the app.

### B. Configure Local Sandbox Credentials

- [ ] **YOU: While still in the Sandbox, open Developers > API keys and copy its publishable and secret keys.** Put them only in your untracked local `.env` file as `STRIPE_CONNECT_PUBLIC_KEY=pk_test_...` and `STRIPE_CONNECT_SECRET_KEY=sk_test_...`. Never paste them into this document, chat, committed files, or the mobile app source.
- [ ] **YOU: Start the Django application with `./run_rentalution`, then install and authenticate the [Stripe CLI](https://docs.stripe.com/stripe-cli).** In a second terminal run:

  ```bash
  stripe login
  stripe listen --forward-to localhost:8000/transaction/stripe/connect/webhook/
  ```

  Leave that command running while testing. Copy the displayed `whsec_...` signing secret into your local `.env` as `STRIPE_CONNECT_WEBHOOK_SECRET=whsec_...`, then restart `./run_rentalution`.
- [ ] **YOU: In the Stripe CLI output, confirm it says it is forwarding to `/transaction/stripe/connect/webhook/`.** Trigger a Sandbox checkout after the engineering work is merged; Stripe CLI should show a delivered event and the app should not report an invalid webhook signature.

### C. Before Live Payments

- [ ] **YOU: Repeat the Connect activation and branding review in [live mode](https://dashboard.stripe.com/connect/overview), using live business details.** Obtain `pk_live_...`, `sk_live_...`, and a separate live `whsec_...` only when the release gate below is signed off.
- [ ] **YOU: Store live keys in the production secret manager/environment only.** Set `STRIPE_CONNECT_PUBLIC_KEY`, `STRIPE_CONNECT_SECRET_KEY`, and `STRIPE_CONNECT_WEBHOOK_SECRET` there; do not use test values on production and do not use live values locally.
- [ ] **YOU: Approve one controlled, real rental as the live smoke test.** Use a small legitimate payment, verify the renter charge, Rentalution fee, Stripe fee, lender transfer, and full-deposit release in Stripe and the application ledger before inviting broader use.

## 1. Stripe Platform Setup

- [x] **ENGINEERING: Validate configured Stripe credentials at startup without logging their values.**
- [x] **ENGINEERING: Verify webhook signatures and log only safe event identifiers/statuses.**
- [x] **ENGINEERING: Document the supported UK/GBP configuration and reject unsupported lender payout configurations in the product.**

## 2. Data Model And Ledger

- [x] Add lender profile fields: connected-account ID, onboarding state, charges/payouts capability state, and last account sync time.
- [x] Add a settlement ledger model linked to a transaction with gross amount, Stripe fee, net transfer, Stripe object IDs, state, failure reason, and idempotency key.
- [x] Add transaction references for the rental transfer and deposit-award transfer.
- [x] Preserve existing `PaymentAttempt` records for payment-provider events; do not use notes as the settlement source of truth.
- [x] Create migrations and admin views for the new ledger.

## 3. Lender Express Onboarding

- [x] **ENGINEERING: Add an authenticated lender action to create/reuse an Express connected account.**
- [x] Generate a Stripe-hosted Account Link with refresh and return URLs.
- [x] Add a lender payout-status panel in web and mobile clients.
- [x] Block paid listings/paid booking acceptance until the lender can receive transfers.
- [x] Add webhook/account-sync handling for onboarding completion, disabled accounts, and changed requirements.

## 4. Rental Payment And Hold

- [x] Continue charging the renter on the platform account for rental + delivery + service fee.
- [x] Associate the PaymentIntent, Charge, and later lender transfer with one transaction transfer group.
- [x] Capture and persist the Stripe Balance Transaction fee and net value after the rental charge settles.
- [x] Do not transfer rental proceeds at checkout or collection handover.
- [x] Keep the deposit as a separate manual authorization.

## 5. Successful Return Settlement

- [x] Trigger settlement only after return handover PIN/QR verification.
- [x] Create one idempotent transfer to the lender's Express account for rental + delivery.
- [x] Use the rental Charge as Stripe `source_transaction` so transfer availability follows the charge.
- [x] Record pending, succeeded, failed, and retried transfer outcomes.
- [x] Notify both parties with the gross lender amount and payment status.

## 6. Deposit Settlement

- [x] Full return: cancel the authorization and record a zero-value borrower release; do not create a lender transfer.
- [x] Agreed partial return: capture only the retained amount.
- [x] Dispute: wait for the final award before capture.
- [x] Retrieve the captured deposit Charge's Balance Transaction before transfer.
- [x] Transfer `max(0, award - actual Stripe processing fee)` to the lender.
- [x] If the award is below the Stripe fee, transfer zero and record the Rentalution shortfall.
- [x] Do not capture/transfer twice on retries or duplicate webhooks.

## 7. Terms, Product UI, And Reporting

- [ ] Update lender terms: processing costs for an awarded deposit retention are deducted from the lender settlement, capped at the award.
- [ ] Update renter terms: full deposit release is an authorization cancellation; partial/dispute deductions follow agreed or adjudicated award rules.
- [ ] Obtain legal review of the lender deduction wording, consumer terms, holding funds, and marketplace responsibilities.
- [x] Show a clear breakdown on the transaction: renter paid, service fee, Stripe cost, lender rental transfer, deposit award, lender deposit transfer.
- [x] Add staff reporting for gross volume, service-fee revenue, Stripe fees, lender transfers, held funds, shortfalls, failures, and retries.

## 8. Test Plan

**Sandbox matrix evidence (18 Sep 2026):** `run_stripe_connect_matrix` options 2 and 3 passed: 3-day Visa debit, 7-day Visa credit, 30-day Mastercard credit, and 31-day Visa debit deposit handling; generic-decline and insufficient-funds decline coverage also passed. The command cancelled short/standard authorisations and fully refunded the long-rental capture. This proves the Stripe card/deposit primitives and policy tiers; the transaction-ledger, Express onboarding, transfer, webhook-replay, and reconciliation scenarios below remain open.

- [ ] Stripe test-mode: Express onboarding completion and incomplete/disabled account cases.
- [ ] Successful rental: verify gross renter charge, actual Stripe fee, and lender rental transfer.
- [ ] Full deposit return: verify cancelled authorization and no deposit capture/transfer.
- [ ] Agreed partial return: verify capture, actual fee, lender net deposit transfer, and ledger figures.
- [ ] Award below Stripe fee: verify zero lender deposit transfer and recorded platform shortfall.
- [ ] Dispute award: verify no capture before decision and correct capture/transfer afterward.
- [ ] Duplicate action, task retry, and webhook replay: verify exactly one charge/capture/transfer per entitlement.
- [ ] Transfer failure/insufficient platform balance: verify pending state, staff visibility, and safe retry.
- [ ] Mobile and web workflow parity tests.

## 9. Release Gates

- [ ] Test dashboard reconciliation matches the local settlement ledger for every test scenario.
- [ ] Webhook signature verification and idempotency tests pass.
- [ ] **YOU: Arrange legal review of the lender-deduction terms, consumer terms, fund-holding approach, and marketplace responsibilities.**
- [ ] **YOU: Read and approve Stripe's [Connect account requirements](https://docs.stripe.com/connect/required-verification-information), [payout guidance](https://docs.stripe.com/connect/payouts), and [separate charges and transfers guidance](https://docs.stripe.com/connect/separate-charges-and-transfers).** Confirm Rentalution can meet any reserve, dispute, verification, or negative-balance obligations before live launch.
- [ ] **YOU: Approve the controlled live smoke test only after the engineering checks above and legal review are complete.**
