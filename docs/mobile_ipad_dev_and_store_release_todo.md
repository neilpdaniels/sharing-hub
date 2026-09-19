# Mobile: iPad development and store-release TODO

This is the single checklist for launching Rentalution on a physical iPad in development and releasing the same Flutter app on the Apple App Store and Google Play.

## 1. Run the development app on the iPad Air

### Compatibility gate

- [ ] On the iPad, open **Settings → General → About** and record **Model Name** and **iPadOS Version**.
- [ ] Confirm it supports iPadOS 13 or later. This project currently has an iOS deployment target of **13.0** in `ios/Runner.xcodeproj/project.pbxproj`.
- [ ] An **iPad Air 2** meets this requirement; update it to the newest iPadOS version it offers before testing.
- [ ] If it is the original iPad Air (2013, maximum iOS 12), stop: this build cannot be installed on it. Use an iPad Air 2 or newer / another iPad that runs iPadOS 13+.

### One-time Mac setup

- [ ] Use a Mac. A physical iPad can only be built, signed, and installed from macOS with Xcode; Linux and Windows cannot do this part.
- [ ] Hardware decision: an **A2289** (13-inch Intel MacBook Pro, 2020, two Thunderbolt ports) is adequate for direct iPad Air 2 debug testing, assuming it has a healthy battery/storage and can run a compatible Xcode. It is **not** a long-term App Store release machine: it is not on Apple's macOS Tahoe 26 compatibility list, and App Store submissions currently require Xcode 26+ / the iOS 26 SDK. Buy it only if it is inexpensive and primarily for device testing; prefer an Apple-silicon Mac, or at least a Tahoe-compatible Mac, for the complete iOS release workflow.
- [ ] Install Xcode, open it once, accept its licence, and install its command-line components. Install Flutter and CocoaPods, then run `flutter doctor` until the iOS section is healthy.
- [ ] Connect the iPad to the Mac by USB, unlock it, and tap **Trust** when asked. In Xcode, confirm it appears under **Window → Devices and Simulators**.
- [ ] On iPadOS 16+, enable **Settings → Privacy & Security → Developer Mode**, restart when prompted, then confirm **Turn On**. Older supported iPadOS versions do not show this setting.
- [ ] In Xcode, open `rentalution_mobile/ios/Runner.xcworkspace`. Select the **Runner** target → **Signing & Capabilities**, sign in with an Apple ID, select its personal team, and allow Xcode to manage signing. A free Apple ID is sufficient for direct debug installation; an Apple Developer Program membership is required for TestFlight/App Store distribution.

### Configure the development endpoint

- [ ] Put the iPad, Mac, and development server on the same trusted Wi-Fi network. Do not expose a local development server to the public internet.
- [ ] Find the LAN IP address of the machine running Django; for example, `192.168.1.155`. Confirm the API is reachable from Safari on the iPad at `http://<LAN-IP>:8000/api/v1/` (a 404/401 is acceptable; a connection error is not).
- [ ] Use a **Stripe test publishable key** and confirm the Django server is using matching Stripe test secret/webhook keys. Never mix a live publishable key with test server keys, or vice versa.
- [ ] The current iOS App Transport Security configuration permits plain HTTP only for `10.0.5.5` and `192.168.1.155`. If the server has another IP, either use HTTPS (preferred) or add that exact development-only IP under `NSExceptionDomains` in `ios/Runner/Info.plist`. Do not add a broad `NSAllowsArbitraryLoads` exception or carry an HTTP exception into the store release.
- [ ] Ensure the iOS Firebase configuration in the Runner bundle is the **development** config. The intended source is `ios/Firebase/dev/GoogleService-Info.plist`; copy it to `ios/Runner/GoogleService-Info.plist` for the dev build. The app will run without Firebase messaging if this is not ready, but push notification testing will not work.

### Launch it

The repository helper `run_rentalution_mobile_dev` uses `--flavor dev`, which is configured for Android only. Do **not** use it for iOS until iOS dev/prod schemes have been added. Use the default Runner scheme instead:

```bash
cd /path/to/rentalution/rentalution_mobile
flutter pub get
flutter devices
flutter run -d <ipad-device-id> \
  --dart-define=APP_NAME="Rentalution Dev" \
  --dart-define=API_BASE_URL="http://<LAN-IP>:8000/api/v1" \
  --dart-define=STRIPE_PUBLISHABLE_KEY="pk_test_..."
```

- [ ] Replace `<ipad-device-id>` with the ID listed by `flutter devices` and `<LAN-IP>` with the actual development-server address.
- [ ] Sign in, test image/video upload, location, biometrics, push registration, and the Stripe test-card journey on the actual iPad.
- [ ] Keep the terminal running for hot reload (`r`) and hot restart (`R`). Stop it with `q` when done.
- [ ] Later: add an explicit iOS `dev` scheme/bundle ID (for example `com.rentalution.mobile.dev`) and an Xcode build phase that selects the matching Firebase plist. This avoids a development build overwriting the production app on the same iPad.

## 2. Shared release readiness

- [ ] Decide and freeze the production identifiers: iOS bundle ID and Android application ID are presently both `com.rentalution.mobile`. They must be unique and cannot be casually changed after store publication.
- [ ] Replace the placeholder production Firebase files with real production-project downloads. Android expects `android/app/src/prod/google-services.json`; iOS expects `ios/Firebase/prod/GoogleService-Info.plist`, copied into the Runner bundle for the production archive.
- [ ] Configure Firebase Cloud Messaging for both stores: production Android app registration plus the iOS bundle ID, APNs authentication key/certificate, and tested production push delivery.
- [ ] Use only `https://rentalution.co.uk/api/v1` and the live Stripe **publishable** key in release builds. Confirm the server has the matching live Stripe secret key and webhook endpoint/secret.
- [ ] Check every permission and declaration against the actual app: camera/photos/video upload, location, biometrics, push notifications, account details, payments, and any analytics/crash reporting.
- [ ] Prepare a public privacy-policy URL, support URL/email, account-deletion process, store description, keyword copy, category, age/content-rating answers, release notes, and final screenshots from real devices.
- [ ] Test the full production-like flow on physical iOS and Android devices: registration/login, password reset, camera/video upload, notifications foreground/background, Stripe card setup and 3DS, rental lifecycle, error/offline states, and account deletion.
- [ ] Run `flutter analyze`, Flutter tests, backend tests, and a release build before each upload. Resolve release-blocking errors rather than relying only on debug builds.
- [ ] Increase `version:` in `rentalution_mobile/pubspec.yaml` for every submitted build. The value is currently `1.0.0+1`; the build number after `+` must monotonically increase for each store upload.

## 3. Apple: TestFlight then App Store

- [ ] Enrol the legal account holder in the Apple Developer Program and create/verify the organisation’s App Store Connect account, banking, tax, and agreements.
- [ ] Register the explicit App ID `com.rentalution.mobile` in Apple Developer, enabling Push Notifications and any other genuinely used capabilities.
- [ ] In App Store Connect, create the app record using that same bundle ID. Complete App Information, pricing/availability, age rating, App Privacy, privacy policy, support URL, screenshots, and review contact/demo account details.
- [ ] In Xcode `ios/Runner.xcworkspace`, select the release signing team and confirm the Runner target has the production bundle ID, an iOS deployment target of 13.0 or higher, and valid distribution signing.
- [ ] Select the production Firebase plist for the archive; verify the `GoogleService-Info.plist` actually embedded in Runner is the production one.
- [ ] Build an IPA from macOS:

```bash
cd /path/to/rentalution/rentalution_mobile
flutter pub get
flutter build ipa --release \
  --dart-define=APP_NAME="rentalution" \
  --dart-define=API_BASE_URL="https://rentalution.co.uk/api/v1" \
  --dart-define=STRIPE_PUBLISHABLE_KEY="pk_live_..."
```

- [ ] Upload `build/ios/ipa/*.ipa` using Xcode Organizer or the Transporter app. Wait for App Store Connect processing to finish.
- [ ] First release to **TestFlight internal testing**, then test all critical paths. Use external TestFlight testing if useful; complete its review requirements where prompted.
- [ ] Create the App Store version, attach the tested build, complete compliance/export questions accurately, submit for review, and choose manual or automatic release after approval.

## 4. Android: internal testing then Google Play

- [ ] Create/verify the Google Play Console developer account and create the app with package name `com.rentalution.mobile`. Do this before an external distribution—Google Play package names are permanent.
- [ ] Create a dedicated upload keystore and store it securely outside Git and outside the repository. Set up a local/CI `key.properties` or secret store to reference it.
- [ ] Change `android/app/build.gradle.kts` so the `release` build uses the upload/release signing configuration. It currently uses the **debug** signing key, which is a release blocker.
- [ ] Confirm the production Firebase configuration is genuine at `android/app/src/prod/google-services.json` and that production FCM works.
- [ ] In Play Console, complete App content: privacy policy, Data safety declarations, content rating, target audience, ads declaration, app access/review credentials, and store listing. Follow any testing requirement the Console presents for this developer account before requesting production access.
- [ ] Build the signed production Android App Bundle:

```bash
cd /path/to/rentalution/rentalution_mobile
flutter pub get
flutter build appbundle --flavor prod --release \
  --dart-define=APP_NAME="rentalution" \
  --dart-define=API_BASE_URL="https://rentalution.co.uk/api/v1" \
  --dart-define=STRIPE_PUBLISHABLE_KEY="pk_live_..."
```

- [ ] Upload `build/app/outputs/bundle/prodRelease/app-prod-release.aab` to the **Internal testing** track first. Install it from the Play test link and test the same critical paths as iOS.
- [ ] Promote through closed/open testing as appropriate, fix pre-launch report issues, then create the production release, set rollout percentage, submit it, and monitor Android Vitals/crashes after release.

## Official references

- Flutter iOS device setup: <https://docs.flutter.dev/platform-integration/ios/setup>
- Flutter iOS release flow: <https://docs.flutter.dev/deployment/ios>
- Flutter Android release flow: <https://docs.flutter.dev/deployment/android>
- Apple build uploads: <https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/>
- Google Play app setup: <https://support.google.com/googleplay/android-developer/answer/9859152>
