# Overdue collection and return confirmation

Website and mobile use the same date-derived workflow flags, in the Europe/London timezone. The complete agreed collection/return day is allowed; the warning starts the following day.

- Enquiry, agreement or checkout verification past the collection date, without a verified collection: “Past agreement date, transaction presumed not to occur”. Either participant can confirm that collection did not happen. This cancels the booking, records who confirmed, releases date reservations and adds a transaction message. If collection happened, participants can instead finish the existing collection verification.
- Ongoing rental or return verification past the return date, without a verified return: ask whether the renter returned the item. Both parties see the warning. Only the lender can report non-return; this opens the existing missing-return dispute case and admin review. If returned, complete the existing return evidence and verification.
- Completed, cancelled and disputed transactions do not show these overdue prompts. A verified collection cannot be cancelled using the no-collection action; a verified return cannot be reported missing.

The existing `auto_cancel_overdue_first_day_bookings` Celery entry is retained for schedule compatibility but now only refreshes booking statistics. It no longer cancels bookings without participant confirmation. Warnings and actions do not depend on the worker running, and live transaction polling picks up date boundaries.

No additional schema migration is needed for these overdue flags. Deploy the backend/static changes and install an updated mobile app. Previously cancelled records are not automatically reopened. Confirmation does not itself charge or refund a payment.
