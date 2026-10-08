# Transaction notification map

This is the source-of-truth map for borrower/renter and lender notifications around a rental transaction. Update it whenever a workflow action or message changes.

## Delivery rules

| Channel | When it is sent | Notes |
| --- | --- | --- |
| Transaction-page message | Every `TransactionMessage` is visible to its recipient in the transaction thread (apart from private dispute messages). | System messages display as **Rentalution**. |
| Website alert | Any unread transaction message increments the message alert. Actionable rental states also appear in the notification bell/notifications page. | A new enquiry is labelled **Review new rental enquiry**. |
| App alert (push) | Every new transaction message attempts an FCM push after the database transaction commits. | Requires an active device and the relevant notification preference. Enquiries use `notify_transaction_enquiry`; all other messages use `notify_transaction_messages`. |
| Email | A transaction message sends email only when `email_to_recepient=True`; all system-generated messages are automatically marked this way. | Email is a branded Rentalution email with a transaction link. It requires the Celery worker. |
| Scheduled lifecycle email | These are direct branded emails, rather than transaction-thread messages. | Requires Celery Beat and worker. |

Users can change these choices in **My details → Notifications**. Important rental-update emails default to on; emails for every conversation message default to off. App preferences include a master app-alert switch plus separate enquiry and transaction-message switches, applied to all active devices for the account.

## Main rental journey

| Event | Recipient | Transaction-page message / exact subject | Website + app alert | Email |
| --- | --- | --- | --- | --- |
| Renter sends enquiry | Lender | **New rental enquiry for {item}**; renter’s supplied text, or **New enquiry {reference}** / “You have a new enquiry on your listing.” | Yes; bell label: **Review new rental enquiry**. Push is classified as an enquiry. | Yes |
| Lender accepts enquiry | Renter | No dedicated message from acceptance itself. | Actionable agreement state becomes visible. | No dedicated email |
| Lender confirms contract | Renter | **Rental Agreement - Please Confirm {reference}**. Includes item, dates, daily price, deposit and 24-hour confirmation deadline. | Yes | No (ordinary user-authored-style message has push, but no email flag) |
| Lender re-sends contract | Renter | **Rental Agreement - Re-sent (Please Confirm) {reference}**. Same terms and deadline. | Yes | No |
| Renter confirms contract | Lender | **Rental confirmed {reference}** / “The borrower confirmed the rental agreement.” | Yes | Yes, because it is system generated |
| Both contracts confirmed | Both | No extra thread message. | No extra alert beyond the confirmation message/state. | **Your rental is good to go · {item}**. Explains collection and return process, dates, collection note/location and links to rental details. Sent once. |
| Day before collection | Both | No thread message. | No | **Collection is tomorrow · {item}**. “Check the agreed collection time and location… lender records checkout evidence… complete handover using the one-time PIN / QR code.” Sent once. |
| Lender submits checkout evidence | Renter | **Checkout evidence submitted {reference}** / “Lender submitted rental-start evidence. Borrower should confirm agreement or submit counter-evidence.” | Yes | Yes |
| Rental/deposit payment is not confirmed | Lender | No automatic message. | Website safety panel and app API say **Do not hand over the item** and identify rental payment and/or deposit as not confirmed. PIN is withheld. | No |
| Renter accepts checkout evidence | Lender | **Checkout evidence accepted {reference}** / “Borrower accepted checkout evidence. Lender can now verify the handover PIN.” | Yes | Yes |
| Renter submits checkout counter-evidence | Lender | **Checkout counter-evidence submitted {reference}** / “Lender should review and complete handover PIN verification.” | Yes | Yes |
| Lender verifies collection PIN | Renter | **Rental started {reference}** / “Checkout handover PIN verified by lender. Rental is now officially ongoing.” | Yes | Yes |
| Day before return | Both | No thread message. | No | **Return is tomorrow · {item}**. Covers agreeing return time/location, return evidence and PIN / QR handover. Sent once. |
| Renter submits return evidence | Lender | **Return evidence submitted {reference}** / “Lender should review the return evidence…” | Yes | Yes |
| Lender accepts return evidence | Renter | **Return evidence accepted {reference}** / “Ask lender for the return verification PIN…” | Yes | Yes |
| Lender submits return counter-evidence | Renter | **Return counter-evidence submitted {reference}** / “Please review and then submit the return verification PIN…” | Yes | Yes |
| Renter verifies return PIN | Lender | **Return handover verified {reference}** / “Return is confirmed and deposit resolution can now proceed.” | Yes | Yes |
| Lender proposes full deposit return | Renter | **Full deposit return proposed {reference}** / amount-specific confirmation. | Yes | Yes |
| Lender proposes reduced deposit return | Renter | **Deposit return proposal {reference}** / proposed amount, explanation and “Please review and either agree or contest.” | Yes | Yes |
| Renter accepts proposal | Lender | **Deposit proposal accepted {reference}** / accepted amount. | Yes | Yes |
| Renter contests proposal | Lender | **Deposit proposal contested {reference}** / “Lender can revise proposal or escalate to admin dispute.” | Yes | Yes |
| Deposit dispute raised/escalated | Other party; then both for an automated status transition | **Deposit dispute raised to admin {reference}** or **Deposit dispute auto-escalated {reference}**. | Yes | Yes |

## Exceptions and admin/dispute events

| Event | Recipient | Current text | Delivery |
| --- | --- | --- | --- |
| Lender declines enquiry | Renter | **Enquiry declined {reference}** / “Your rental enquiry was declined.” | Thread, website, app push, email |
| Either party cancels an enquiry | Other party | **Transaction Cancelled - {reference}** plus the supplied reason. | Thread and app push; no email unless marked system-generated elsewhere |
| Renter rejects contract | Lender | **Rental Agreement Rejected {reference}** / “Borrower has rejected the rental agreement.” | Thread and app push |
| Borrower reports missing collection | Lender | **Missing rental reported {reference}** / transaction voided; dispute/admin review required. | Thread, website, app push, email |
| Lender reports non-return | Renter | **Missing return reported** / “The lender confirmed the item was not returned. Non-return dispute review is now open.” | Thread, website, app push, email |
| Staff marks dispute under review | Both | **Dispute under review {reference}** / keep evidence and messages on-platform. | Thread, website, app push, email |
| Staff resolves dispute | Both | **Dispute resolved {reference}** / outcome, deposit return, closure and notes. | Thread, website, app push, email |
| Payout/deposit settlement completes or needs attention | Both | e.g. **Rental Proceeds settlement complete {reference}** or **Deposit award settlement pending {reference}**. | Thread, website, app push, email |

## Scheduled reminders

The `send_pending_action_reminders` task runs hourly at five minutes past the hour, only within the configured 09:00–20:00 local reminder window.

| Pending event | Recipient | Default cadence | Current text summary |
| --- | --- | --- | --- |
| Lender has signed; renter has not | Renter | Every 4 hours | **Contract confirmation reminder {reference}**; confirms remaining time in the 24-hour window. |
| Lender has not signed first | Lender | Every 12 hours | **First signature reminder {reference}**; asks lender to sign and start the other party’s 24-hour window. |
| Return PIN exists but is unverified | Renter | Every 4 hours | **Return verification reminder {reference}**; asks for PIN submission and gives time remaining. |
| Feedback is outstanding | Party/parties who have not left feedback | Every 4 hours | **Feedback reminder {reference}**; gives time before automatic closure. |
| Deposit proposal/contest is pending | Renter or lender, as applicable | Every 4 hours | **Deposit return proposal pending** or **Deposit contest pending**; says the case may escalate and shows time left today. |

## Deliberate noise reduction

Routine status changes no longer create automatic thread messages: agreement created, rental day, rental started, return day, deposit-review state, feedback state, and normal completion. Important exceptions still do: cancellation, contested deposit, dispute opening/decision and related settlement failures.

## Operational checks

1. A website notification needs an unread transaction message or an actionable state; it is not a separate persistent notification model.
2. Push is attempted, not guaranteed: FCM credentials, an active mobile-device token and the user’s enabled preference are required.
3. Email is queued through Celery. If the worker is down, it will not send until the queue is processed.
4. The collection PIN is the hard safety gate: it is not exposed or verifiable until rental payment and deposit are confirmed.
