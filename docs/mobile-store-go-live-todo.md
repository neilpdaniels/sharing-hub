# Mobile app go-live TODO: iOS and Android

This is the operational checklist for releasing `rentalution_mobile` to the App Store and Google Play. It is deliberately ordered: do the shared blockers first, then the two store tracks. Check off an item only when there is evidence (a screen recording, a test result, an uploaded build, or a saved credential).

## Release decision and ownership

- [ ] Name a release owner, a technical release owner, and an out-of-hours contact for the first week after launch.
- [ ] Decide the first release countries, whether the rollout is phased, and whether the release will be manual after approval.
- [ ] Freeze the first-store-release scope. Defer non-essential features rather than adding them during the store-review window.
- [ ] Confirm the permanent production identifiers before creating either store record: the project currently uses `com.rentalution.mobile` for both the Android application ID and iOS bundle ID. They must match the store records and cannot be casually changed after publication.
- [ ] Increase `version:` in `rentalution_mobile/pubspec.yaml` for every uploaded build. The part after `+` is the monotonically increasing build number used by both stores.

## Shared production readiness

### Production configuration and secrets

- [ ] Use release-only build commands with `API_BASE_URL=https://rentalution.co.uk/api/v1` and the live, publishable Stripe key. Do not put Stripe secret keys, Apple private keys, Android keystores, Firebase service-account files, or production `.env` files in Git or in a Dart define.
- [ ] Confirm the production Django environment has matching live Stripe server keys and webhook endpoint/secret; make a live-mode test booking using low-value test inventory before submission.
- [ ] Replace/verify the production Firebase configurations: `android/app/src/prod/google-services.json` and `ios/Firebase/prod/GoogleService-Info.plist`. Verify the right production iOS plist is copied into the Runner bundle before archiving.
- [ ] Configure production App/Universal Links: set `APPLE_APP_LINK_TEAM_ID` and `ANDROID_APP_LINK_SHA256` to the production values, publish the matching association files, then set `MOBILE_APP_LINKS_REQUIRED=1` for the production deployment and test links from both stores' builds.
- [ ] Configure Firebase/APNs for the production bundle ID and verify notifications in foreground, background, and after a cold start on real Android and iPhone devices.
- [ ] Check the production app never falls back to a development API or test Stripe key. Deliberately cause an API failure and ensure the error shown is safe and helpful.
- [ ] Confirm TLS works for the production API and that no development-only iOS HTTP exception is present in the release `Info.plist`.

### Legal, support, and store content

- [ ] Publish a public privacy-policy URL, Terms and Conditions URL, support URL/email, and a clear account-deletion path. Test all links from a phone that is not signed in.
- [ ] Prepare a reviewer test account that can complete the important flows, plus clear App Review / Play Console instructions. Do not require a reviewer to provide a UK mobile number, a real payment card, or a real identity document without an alternative test path.
- [ ] Prepare final store assets: app name, subtitle/short description, full description, keywords (Apple), category, contact details, release notes, 1024px icon, feature graphic (Android), and current screenshots from real devices.
- [ ] Complete declarations from the actual shipped app and SDKs, not assumptions: camera/photos/video upload, precise or approximate location, biometrics, push notifications, account/profile data, payment details handled by Stripe, analytics/crash reporting, and user-generated content/messaging.
- [ ] Confirm moderation, reporting, blocking, and support escalation are usable for listings, messages, uploaded media, and any other user-generated content. This is especially important for a peer-to-peer marketplace.

### Product, payments, and safety test pass

- [ ] Run `flutter pub get`, `flutter analyze`, Flutter unit/widget/integration tests, and relevant Django/API tests. Capture the exact commit SHA and the test results in the release ticket.
- [ ] Test release builds on physical current Android and iOS devices, not only simulators: registration, login/password reset, email/mobile verification, browse/search, list an item, photos/video upload, location, QR/PIN handover, messaging, notifications, Stripe/3DS, rental/deposit lifecycle, dispute/return flow, account deletion, logout, offline/error states, and app update from an earlier build.
- [ ] Check accessibility basics: scalable text, VoiceOver/TalkBack labels, touch target sizes, keyboard focus, colour is not the only status signal, and important error messages are announced.
- [ ] Put server monitoring, error alerting, payment/webhook alerting, database backup checks, rate limits, and a first-week incident/rollback plan in place.

## Android: Google Play

### One-time console and signing setup

- [ ] Create or verify the Google Play Console developer account and create the app using `com.rentalution.mobile`. Package names are permanent in Play once used.
- [ ] Create a dedicated upload keystore, retain its alias/password in the approved secret store, and enable Play App Signing. Keep an offline recovery copy under restricted access.
- [ ] **Resolve the current release blocker:** `android/app/build.gradle.kts` signs `release` with the debug key. Replace this with a release signing configuration that reads a local/CI secret `key.properties`; keep that file and the keystore out of Git. Build and install a signed release to prove it works.
- [ ] Confirm `targetSdk` from the installed Flutter/Android toolchain meets the current Google Play target API requirement; this changes annually, so verify it in Play Console before uploading.
- [ ] Create the production app record and complete Store listing, App content, Data safety, content rating, target audience, ads declaration, app access/reviewer instructions, and privacy policy. Answer Data safety from the actual app and its SDKs.

### Build, test, and publish

- [ ] Build the signed production Android App Bundle from the release commit:

  ```bash
  cd rentalution_mobile
  flutter pub get
  flutter analyze
  flutter build appbundle --flavor prod --release \
    --dart-define=APP_NAME=rentalution \
    --dart-define=API_BASE_URL=https://rentalution.co.uk/api/v1 \
    --dart-define=STRIPE_PUBLISHABLE_KEY=pk_live_...
  ```

- [ ] Upload `build/app/outputs/bundle/prodRelease/app-prod-release.aab` to **Internal testing**. Install using the opt-in URL on several real devices and complete the shared test pass.
- [ ] Review Android vitals, crash/ANR data, device compatibility, and the automated pre-launch report. Fix critical findings and upload a new build number where needed.
- [ ] Move to closed testing if the account/Play Console requires it, collect tester feedback, and confirm production access is available before announcing a launch date.
- [ ] Create the production release with a small staged rollout (for example 5–10%), submit it, and monitor crashes, ANRs, authentication, uploads, notifications, payment errors, and support contacts before expanding the rollout.

## iOS: TestFlight and App Store

### One-time Apple setup

- [ ] Enrol the legal account holder/organisation in the Apple Developer Program. In App Store Connect, complete agreements, banking, tax, and team roles.
- [ ] Register the explicit App ID `com.rentalution.mobile` in Apple Developer and enable only the capabilities used (notably Push Notifications). Create the matching App Store Connect app record.
- [ ] Use a current, App Store-supported Xcode/macOS environment. Apple changes its upload/build requirements; validate the current requirement immediately before the archive rather than relying on an old Mac/Xcode setup.
- [ ] In `ios/Runner.xcworkspace`, set the correct distribution team and confirm the release bundle identifier, Push Notifications entitlement, production Firebase plist, release icon, and `IPHONEOS_DEPLOYMENT_TARGET` (currently 15.0) are intentional.
- [ ] Complete App Store Connect App Information: category, age rating, pricing/availability, privacy policy, support URL, App Privacy nutrition label, screenshots, copyright, review contact, demo account, and reviewer notes. Answer export-compliance/encryption questions truthfully.

### Build, TestFlight, and submit

- [ ] From macOS, archive the exact release commit:

  ```bash
  cd rentalution_mobile
  flutter pub get
  flutter analyze
  flutter build ipa --release \
    --dart-define=APP_NAME=rentalution \
    --dart-define=API_BASE_URL=https://rentalution.co.uk/api/v1 \
    --dart-define=STRIPE_PUBLISHABLE_KEY=pk_live_...
  ```

- [ ] Upload the IPA in Xcode Organizer or Transporter. Wait for App Store Connect processing; resolve any signing, icon, privacy-manifest, encryption, or validation warnings before testing.
- [ ] Release first to internal TestFlight testers, then use external TestFlight only if useful. Test the processed TestFlight build with the shared test pass, including push notifications and payment authentication.
- [ ] Attach the tested build to the App Store version, recheck every metadata field and reviewer credential, submit for review, and select manual release so the launch can be coordinated.
- [ ] Once approved, release deliberately and monitor App Store Connect crashes, reviews, support traffic, sign-in failures, notifications, uploads, and payments during the first week.

## Release-day and rollback runbook

- [ ] Announce only after both store links/install paths, monitoring, support cover, and status-page messaging are ready.
- [ ] Check the first install, registration, push token, listing upload, booking, and payment event in production from each store build.
- [ ] Define stop conditions before rollout: payment loss, security/privacy issue, elevated crash/ANR rate, broken authentication, or a critical booking/deposit-flow error. Name the person authorised to pause Android rollout or remove the iOS app from sale.
- [ ] Preserve the prior working backend migration/release path and a support template for known issues. Mobile binary rollback is slow; use server-side feature flags or safe degradation where possible.

## Primary official references

- Apple: [uploading builds](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/), [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/), and [app privacy](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy/).
- Google: [create and set up an app](https://support.google.com/googleplay/android-developer/answer/9859152), [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469), and [target API level](https://developer.android.com/google/play/requirements/target-sdk).
- Flutter: [Android deployment](https://docs.flutter.dev/deployment/android) and [iOS deployment](https://docs.flutter.dev/deployment/ios).
