# Rentalution: pre-publication working to-do

**Goal:** make the public website presentable for Apple Developer review, while continuing the Google Play submission.  Do not remove the website password protection until the catalogue is intentionally reduced and the public-page checks below have passed.

**Launch catalogue rule (agreed 6 November 2026):** start with a small, intentional set of strong rental areas and build up from real demand. This is a whitelist exercise, not an attempt to retain every existing seeded category. Remove areas that are cheap to buy, safety/hygiene-sensitive, sparse, or not credible for the initial marketplace.

This is the short working list distilled from [the full mobile store checklist](mobile-store-go-live-todo.md) and [the catalogue AI notes](catalog-ai-follow-ups.md).  The longer checklist remains the source of detailed release requirements.

## 1. Catalogue cleanup — first priority

- [x] Confirm the catalogue-review code and its migrations are deployed to production, with the worker/AI configuration enabled (`CATEGORY_AI_ENABLED=1`). Verified 6 November 2026: migrations through `0013` applied; web and `catalog-ai-worker` healthy; AI key present; Celery workers responding.
- [ ] Produce a top-level catalogue inventory (category, product-template count, live-listing count and completed-rental count), then explicitly choose the small launch whitelist before making broad deletions.
- [ ] In Django admin, run a **Heavy product-worthiness review**: `Navigation → Product catalogue reviews → Run product review`.
- [ ] Wait for the review to become **Ready for human review**; investigate and fix configuration/worker errors if it becomes **Failed**.
- [ ] Review every AI recommendation. Apply only clearly safe duplicate consolidations or low-value retirements; keep products with rental/order history unless a separately planned migration supports the change.
- [ ] Run a **Medium taxonomy review**: `Navigation → Catalogue taxonomy reviews → Run catalogue review`.
- [ ] Human-review its proposed category merges/removals and apply only changes that improve browsing. Do not let the AI apply changes automatically.
- [ ] Browse the resulting live catalogue on phone and desktop: main categories, search, product pages, images, empty states, and no broken links.
- [ ] If the AI review cannot be run or produces poor recommendations, perform the same reduction manually: remove obvious duplicates and low-value/generic items first, recording each keep/remove decision.

**Definition of done:** the catalogue feels deliberately curated, has no obvious duplicate product names, and its categories are easy to understand for a first-time visitor.

## 2. Make the website ready to be public

- [ ] Check the signed-out public pages: home, catalogue/search, product pages, About/How it works, contact/support, Terms, and privacy policy.
- [ ] Update the privacy policy so it explicitly covers the mobile app, Google sign-in, user/listing/message/address data, uploaded media, location, Stripe, Firebase/push notifications, processors, retention, and international processing where applicable.
- [ ] Publish a public account-deletion page explaining the request process, deleted data, lawful retention (e.g. disputes/fraud), and retention periods. Link it from both the app and privacy policy.
- [ ] Verify the privacy policy, terms, support/contact, and deletion URLs in a signed-out/incognito browser. They must be HTTPS and must not redirect to login.
- [ ] Verify the public site has no test content, broken media, internal/admin links, placeholder copy, or accidental secrets.
- [ ] Take a dated backup/snapshot and record how to restore Basic Auth before changing access.
- [ ] Remove the Nginx `auth_basic` protection from the production `location /` block, reload Nginx, and test the site on mobile and desktop while signed out. Keep `/healthz/`, Stripe webhook, app-link association files, and payout-return routes working.

**Definition of done:** anyone (including Apple reviewers) can access a polished public website without a password, while sensitive admin areas remain protected by application login.

## 3. Apple Developer reapplication / App Store preparation

- [ ] Reapply for the Apple Developer Program using the legal account holder/organisation details; retain the application/reference details and respond promptly to Apple requests.
- [ ] Once accepted, verify the App ID and App Store Connect record use `com.rentalution.mobile`.
- [ ] Add the real production iOS Firebase `GoogleService-Info.plist` and validate push notifications on a physical iPhone.
- [ ] Verify Universal Links with the Apple Team ID and production association file; only then enable `MOBILE_APP_LINKS_REQUIRED=1`.
- [ ] Prepare App Store Connect metadata: privacy nutrition label, age rating, category, support/privacy URLs, screenshots, reviewer contact, demo account, and clear reviewer notes.
- [ ] Build an internal TestFlight build using the live API and live Stripe publishable key; run the physical-device test pass from the full checklist.

## 4. Continue the Google Play application

- [ ] Confirm the published privacy-policy URL and new account-deletion URL are publicly accessible while signed out.
- [ ] Finish Play Console: Sign-in details, Ads, Content rating, Target audience, Data safety, Government apps, Financial features, Health, category/contact details, Store Listing, reviewer account/instructions, and screenshots.
- [ ] Create and securely back up the Android upload keystore; configure the four `ANDROID_RELEASE_KEYSTORE` values outside Git and prove a signed production bundle installs.
- [ ] Verify the production Android Firebase configuration and App Links (including the release certificate SHA-256); then enable `MOBILE_APP_LINKS_REQUIRED=1` after validation.
- [ ] Bump the Flutter build number, build the production AAB with the live API/Stripe publishable key, and upload it to Google Play Internal testing.
- [ ] Test the Play-installed build on real Android devices, review pre-launch/vitals results, resolve critical findings, then progress through the required testing track toward production.

## 5. Shared release gate — before inviting real users

- [ ] Test physical Android and iPhone release builds: registration/sign-in, verification, browse/search, listing/photo/video upload, location, messages, notifications, Stripe/3DS, booking/deposit, handover/return/dispute, deletion, logout, and offline/error states.
- [ ] Confirm production monitoring, error/payment-webhook alerts, backups, rate limits, support cover, rollback plan, and first-week release owner.
- [ ] Choose launch countries, staged rollout percentage, and manual versus automatic release.

## Next working session

1. Confirm the production deployment and AI settings for the product catalogue review.
2. Run the Heavy review and evaluate its recommendations together before anything is removed.
3. Work through the public-page/legal checks, then remove Basic Auth deliberately.
