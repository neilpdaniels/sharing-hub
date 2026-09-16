# Mobile / website transaction workflow parity

## Completed

- [x] Trace website templates, HTML action handlers, API payloads, and mobile rendering.
- [x] Use the same server date, role, contract, evidence, and payment prerequisites for available actions.
- [x] Restore lender collection initiation and borrower agreement/counter-evidence.
- [x] Show collection QR/PIN to the borrower; lender scans or enters it to commence rental.
- [x] Show “Rental commenced, awaiting return day on [date]” before return is due.
- [x] Unlock borrower return evidence on the return date while status is still ongoing.
- [x] Let the lender agree with return evidence or submit counter-evidence.
- [x] Show return QR/PIN to the lender; borrower scans or enters it to confirm return.
- [x] Gate deposit acceptance/contest on an actual proposal; retain the five-proposal limit and escalation.
- [x] Skip deposit negotiation when no deposit is held, matching the website.
- [x] Refresh mobile/web action visibility at date rollover without requiring a saved status change.
- [x] Verify HTML rendering, HTML submissions, API transitions, mobile controls, and PIN submission.

## Shared sequence

| Stage | Lender | Borrower |
| --- | --- | --- |
| Before collection day, contracts/card ready | Await rental day | Await rental day |
| Collection due, contracts/card ready | Submit checkout evidence; capture payment and request deposit hold | Await lender evidence |
| Checkout evidence submitted | Await borrower review; retry deposit hold if needed | Agree with lender evidence or upload counter-evidence |
| Evidence reviewed and required funds secured | Scan/enter borrower code to verify collection | Show collection QR/PIN to lender |
| Collection verified, before return date | Rental commenced; display return date | Rental commenced; display return date |
| Return date reached | Await borrower evidence | Submit return evidence |
| Return evidence submitted | Agree or upload counter-evidence; show return QR/PIN | Scan/enter lender code to verify return |
| Return verified, deposit held | Propose return amount, with reason for a deduction | Await proposal, then accept or contest |
| Proposal contested | Update proposal within five-iteration limit, or escalate | Await revised proposal or escalate |
| Return verified, no deposit | Feedback | Feedback |

Dates are evaluated in **Europe/London**, matching the website's existing contract-day boundary. Device timezone does not decide which actions are available. A due date exposes the next step; it does not bypass contracts, card verification, evidence, funds, or handover verification. Same-day rentals unlock return after collection verification.

The mobile app reads `workflow_payload.allowed_actions`, `message`, and `contract_deadline`. The website and API validate handover/date-sensitive submissions against the same model rules. Workflow labels and live-refresh signatures change at day boundaries. The website's refresh signature carries code availability only, never the PIN. QR verification checks the transaction reference as well as the PIN.

## Exception workflow TODO and audit

- [x] Expired borrower confirmation: hide acceptance, show lender re-send action, and use the same deadline in web/API/mobile.
- [x] Missed collection: offer borrower reporting after the start date, including checkout started but PIN never verified.
- [x] Missed return: offer lender reporting after the return date and use the existing dispute path.
- [x] Failed rental capture: keep the transaction agreed so collection submission can be retried; withhold the code.
- [x] Delayed deposit hold: generate the collection code when the background hold succeeds after borrower review.
- [x] Deposit retry: save queued state before dispatch so fast workers cannot have success overwritten.
- [x] Deposit contest/re-proposal and maximum-iteration escalation.
- [x] Existing automatic cancellation of incomplete first-day bookings and feedback-window closure regression checks.
- [ ] Operational recovery exercise with stopped/restarted Celery workers and missed scheduled jobs. Automatic cancellation/reminders require Celery worker and beat; viewing a transaction does not run those jobs.
- [ ] Provider-pending operations: exercise delayed/duplicate/out-of-order callbacks, worker failure during capture/settlement, and reconciliation before retrying a potentially completed payment.
- [ ] Confirmation re-send after the booked start day: the end-of-day deadline is already past; define rescheduling/new-enquiry recovery rather than repeatedly re-sending an expired window.
- [ ] Prolonged inactivity at each evidence/review/verification/deposit stage: audit reminders, participant counts, deadlines, and escalation ownership against this shared action policy.
- [ ] Run the complete evidence-recording, QR-camera scanning, and payment-provider flow on two physical devices after rebuilding the app and restarting the worker.

## Admin and scenario date tools TODO

- [x] Let admin users change a transaction's rental start/end dates from the **website transaction page** (website only, not the mobile app). Staff see **Edit rental dates (admin)** next to the dates. The form validates the range and booking/availability conflicts, requires a reason, and records the admin and new dates in history. Date/history/reservation updates are atomic; existing progress, evidence, codes, and payments stay as recorded. The edit page lists recent date changes. Twelve admin-date tests plus the eight scenario-date tests passed; no live transaction dates were changed.
- [x] Add an interactive menu to `./run_seed_transaction_scenarios`: seed missing scenarios, **Commence today**, **Finish today**, **Reset scenarios**, and cancel. Date moves update recognised existing scenarios using Europe/London's current date, preserve rental length and workflow progress, and update reserved dates. Production use is blocked. Eight Django regression tests and mocked shell-menu checks passed; current scenario data has not been changed by this implementation.

## Validation

- 34 targeted Django tests passed: new web/API parity cases, existing API actions, web workflow extensions, automatic missed-collection cancellation, and reminders.
- 16 mobile regression tests passed, covering server-driven collection/return actions, correct code ownership, PIN submission, QR scanner controls, deposit proposal gating, evidence permissions, and polling without a status change.
- Dart analysis reported no errors; existing warnings/informational notices remain.
- Payment operations are mocked in workflow tests; no live payments or user transactions were altered.
- A broader 41-test transaction run had three failures in other existing expectations: dispute payment offsets (handler explicitly fixes this to zero), rental capture during card setup (capture now belongs to collection), and notification wording (“Rental agreement” versus “Agreement”). These remain follow-up test/business-rule reconciliation items, not a claim that the complete backend suite is green.

## Applying the changes

Rebuild/restart the mobile app against the updated Django backend. Restart the Celery worker to load the deposit-completion fix. No database migration is introduced by this change. An existing APK will not include the new workflow controls.
