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

### Repeatable full-lifecycle runner

For real Stripe Sandbox lifecycle checks without using either frontend, use the
non-production runner below. It resets/recreates only the marked scenario
fixtures, uses a Stripe test card, and prints the resulting PaymentIntent and
transfer IDs plus the recorded fee/net figures. It needs a dedicated, already
enabled Sandbox Connect destination account; do not provide a live `acct_...`
ID or one already linked to a local user profile.

```bash
./run_stripe_lifecycle_scenario --case full-release --execute --destination-account acct_...
./run_stripe_lifecycle_scenario --case partial-award --execute --destination-account acct_...
./run_stripe_lifecycle_scenario --case fee-shortfall --execute --destination-account acct_...
```

Run it once without `--execute` to display its plan. The cases use a £44 renter
charge (£30 rental + £10 delivery + £4 service fee) and an £80 deposit.

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

## 10. Lender Payout Onboarding: Web And Mobile Completion Plan

### Decision and intended money flow

Use **Stripe Connect Express**, not a Rentalution-built BACS integration.

1. A borrower pays Rentalution's Stripe platform account for rental, delivery,
   and the platform fee.
2. Before a user can receive money as a lender, Rentalution creates one Stripe
   Express connected account for them and sends them to Stripe-hosted
   onboarding.
3. Stripe collects and verifies the lender's identity and nominated UK bank
   account. Rentalution must never collect or store their sort code/account
   number itself.
4. After verified return, Rentalution creates a Stripe Transfer for rental and
   delivery to that lender's connected-account balance. A deposit award follows
   the agreed/dispute path and is a separate transfer.
5. Stripe pays the connected-account balance to the lender's nominated bank
   account on its configured payout schedule. The banking rail (for example
   Bacs or Faster Payments where applicable) is Stripe's responsibility; the
   product should promise a Stripe-estimated arrival date, not a particular
   rail or speed.

This project already has the foundation: it creates Express accounts, generates
Stripe Account Links, records `account.updated` state, and transfers funds only
when both Stripe transfer and payout capabilities are active. The remaining
tasks are about making this a complete, understandable product flow and proving
it before live launch.

### When to ask the lender

- [x] Decide and document the business rule: lenders can create a listing, but
  payout setup is mandatory before a lender can accept a paid booking or
  receive a transfer. Do not wait until the return/payout day.
- [x] Allow browsing and drafting a free listing without Stripe onboarding, but
  show an explicit "Payout setup required before this listing can accept paid
  rentals" state.
- [x] If the lender leaves Stripe onboarding unfinished, retain the draft and
  give a safe "Continue payout setup" action. Do not repeatedly create new
  connected accounts.

### Website TODO

- [x] Account page has a **Set up lender payouts** action and opens a
  Stripe-hosted Express Account Link.
- [x] Add a **Payout details** tab to `/my_rentalution/my_details/`. It must
  show payout readiness and a **Change bank/payout details** action. That
  action opens the lender's Stripe Express Dashboard login link (or Stripe
  onboarding for a lender without an account); it must not display, accept, or
  store BACS sort-code/account-number fields in Rentalution.
- [x] Put the payout-readiness call-to-action on listing creation and block
  paid booking acceptance until the lender is payout-ready. Listings do not
  have a separate publish state in the current workflow.
- [x] When a lender creates or publishes a paid listing without payout setup,
  show a blocking, actionable notice: **"Set up lender payouts before this
  listing can accept paid rentals"** with a **Set up payouts** link. Show the
  same notice when they try to accept a paid transaction; preserve the pending
  request but do not let acceptance complete until Stripe confirms payout
  readiness.
- [x] At return/settlement, if a lender still cannot receive payouts, show an
  urgent transaction-level notice: **"Your rental payment is ready. Set up
  payouts to receive it."** Link to payout setup, retain the settlement as
  pending, and show the amount/status in the transaction history until a safe
  idempotent retry succeeds. Alert staff if it remains unresolved.
- [x] Replace raw Stripe requirement field names with plain-language status:
  **Not started**, **Action needed**, **Under review**, **Ready for payouts**,
  or **Restricted**. Keep detailed fields for staff only.
- [x] On the Account Link return page, retrieve/synchronise the connected
  account before showing status; a return to the site is not proof that Stripe
  has finished verification.
- [x] Add a "Continue/update payout details" action. New lenders receive a
  fresh Account Link; existing Express lenders receive a fresh Dashboard login
  link to update their details.
- [x] Show a lender settlement history: transaction, gross rental/delivery,
  deposit award if any, Stripe fee deduction where applicable, and transfer
  status. Stripe payout arrival estimates remain a future enhancement if Stripe
  exposes a suitable account-level value for this flow.

### Mobile app TODO

- [x] Account Details has a **Set up lender payouts** action and launches the
  Stripe-hosted onboarding URL in the device browser.
- [x] Put payout readiness and a direct "Set up/continue payouts" entry point
  in the lender listing/acceptance journey, not only Account Details.
- [x] When a lender creates/publishes a paid listing or attempts to accept a
  paid transaction without payout readiness, show an actionable payout-setup
  message and take them directly to payout setup. The server preserves and
  blocks acceptance of the pending paid request until Stripe confirms
  readiness.
- [x] At return/settlement, surface the same urgent "payment is ready" action
  in the transaction and notifications inbox. Refresh the transaction after
  onboarding and show pending/paid status without allowing a second payout.
- [x] When the user returns from the browser, refresh account status on app
  resume and show the same plain-language statuses as the website. Do not mark
  setup complete merely because the browser link closed.
- [ ] Support a verified HTTPS app/universal link return route (with browser
  fallback) so the user returns to the relevant Account Details screen. The
  application-side route is implemented at
  `https://rentalution.co.uk/app/payouts/return/`; before marking this complete,
  deploy `APPLE_APP_LINK_TEAM_ID` and `ANDROID_APP_LINK_SHA256`, then verify the
  two public association files on the live HTTPS domain with the signed release
  apps. Set `MOBILE_APP_LINKS_REQUIRED=1` for that signed-build deployment so
  production validation enforces both values. Nginx must not apply HTTP Basic Auth to either association URL or the
  return URL (the deployment config includes exact public exemptions). The
  browser fallback is **My details → Payout details**.
- [x] Display outstanding action in a retryable way; do not expose raw Stripe
  requirement keys to the user.
- [x] Add the same settlement/payout history and pending/failed payout notices
  as the website.

### Server, Stripe configuration, and safeguards TODO

- [ ] In Stripe Sandbox, complete Connect platform activation, choose Express,
  and create two test lenders: one fully verified and one deliberately
  incomplete. Confirm `account.updated` webhooks change the local profile
  fields correctly.
- [x] Confirm the exact gate in server-side business logic: a lender without
  active Stripe transfer and payout capabilities cannot accept a paid rental,
  and no rental/deposit transfer proceeds without both capabilities.
- [x] Add a safe, authenticated server endpoint to retrieve the current
  connected-account status on demand; webhook state remains authoritative for
  asynchronous changes.
- [x] Add rate limiting/audit logging to onboarding-link generation and never
  return a connected account ID or Stripe account data that the requester does
  not own.
- [x] Decide the Stripe Express payout schedule and document it in lender
  terms: use Stripe Express's automatic daily payout schedule for available
  funds. Do not build a direct BACS file/payment workflow unless Stripe Connect
  cannot meet a later, documented requirement.
- [x] Add support and operations procedures for failed/paused payouts, changed
  bank details, negative balances, chargebacks, account restrictions, and
  lender offboarding. See the operating procedure below.

### Support operating procedure

- Failed or paused payout: confirm the `StripeSettlement` record and Stripe
  Transfer status; tell the lender to use **Payout details** if their account
  needs action; retry only the failed settlement from staff tooling after the
  account is ready. Never create a manual duplicate transfer.
- Changed bank details: direct the lender to Stripe Express **Payout details**;
  Rentalution staff must not take bank details by message, email, or phone.
- Negative balance, chargeback, or restricted account: pause further paid
  acceptance for that lender, preserve the local ledger/evidence, and escalate
  to the operations owner before attempting retries or off-platform payment.
- Lender offboarding: stop new paid bookings, resolve or refund open
  transactions, confirm all settlement records are final, then retain only the
  audit data required by law and Stripe's terms.

### Approved lender payout wording

Use this wording in lender terms and payout-facing product copy:

> After a rental is settled, Rentalution transfers the lender amount to your
> Stripe Express balance. Stripe automatically pays eligible available funds to
> your nominated bank account on its daily payout schedule. Stripe provides the
> estimated bank-arrival date; Rentalution does not promise a particular banking
> rail, an instant payout, or a guaranteed arrival time.

### Acceptance tests before enabling real lenders

- [ ] Website: new lender starts onboarding, abandons it, resumes it, completes
  it, and becomes eligible for a paid listing/booking only after the capability
  webhook confirms readiness.
- [ ] Mobile: repeat the same flow, including browser return/app resume and a
  device with no usable browser return link.
- [ ] Execute one Sandbox rental/return and verify the platform charge, lender
  Transfer, connected-account balance, and resulting Stripe payout are linked
  to the same lender and transaction in both Stripe and the local ledger.
- [ ] Verify that an incomplete, disabled, or restricted connected account
  cannot receive a transfer and is given a useful recovery message.
- [ ] Have UK payments/legal review approve the final funds-flow description,
  payout timing, Stripe fees/deductions, consumer terms, and support process
  before enabling live payouts.

### Sandbox and device test record

Record the date, tester, Stripe account IDs, transaction reference, and Stripe
object IDs beside each acceptance checkbox above. Never put Stripe secret keys,
bank details, or full card numbers in this file.

1. Configure Stripe **Sandbox** Connect for Express and use the local Stripe
   CLI listener for `account.updated`. Complete onboarding for lender A, leave
   lender B with an outstanding requirement, and confirm the corresponding
   local `Profile` capability fields change only from the webhook/status sync.
2. On the website, sign in as lender A, start payout setup, abandon it, open
   **Payout details** again, and complete it. Confirm a paid enquiry remains
   pending until both transfer and payout capabilities are true; then accept it.
   Repeat the rejection/recovery case with lender B.
3. On a signed Android and iOS build, begin onboarding, return through
   `https://rentalution.co.uk/app/payouts/return/`, and confirm the app opens
   Account Details and refreshes status. Also open that URL where no app-link
   match exists and confirm the browser reaches **My details → Payout details**.
4. For a controlled Sandbox payment/settlement run, use
   `./run_stripe_lifecycle_scenario`, choose the full-release case, and provide
   lender A's enabled `acct_...` account ID. Retain the printed PaymentIntent,
   Transfer, and settlement IDs; check they match the local transaction ledger
   and the lender's connected-account balance. Run the partial-award and
   fee-shortfall cases if those outcomes will be enabled at launch.
5. Before switching live mode, have the named payments/legal approver sign off
   the customer-facing funds-flow, Stripe Express payout timing, fees, and
   support procedure. Record the approval reference outside source control.
