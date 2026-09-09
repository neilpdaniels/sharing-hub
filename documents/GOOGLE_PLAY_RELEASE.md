# Google Play Release Guide

This is a copy-pasteable checklist for shipping the Flutter app in `rentalution_mobile/` to Google Play.

## 1. Prerequisites

Make sure you have:
- a Google Play Console account
- a Google account that can access the Play Console
- Flutter installed and working
- Java / Android tooling installed
- a signing keystore for release builds
- production backend/API settings ready

Useful Play Console URL:
- https://play.google.com/console

## 2. Verify the app builds locally

From the repo root:

```bash
cd /home/neil/Projects/rentalution/rentalution_mobile
flutter pub get
flutter doctor -v
flutter analyze
```

If you want a quick release-mode sanity check on a device or emulator:

```bash
flutter run --release --dart-define=API_BASE_URL=https://your-production-domain/api/v1
```

## 3. Confirm Android package info

Check these files before releasing:
- `rentalution_mobile/android/app/build.gradle.kts`
- `rentalution_mobile/pubspec.yaml`

You want:
- a stable `applicationId`
- a sane version name and build number
- the production API base URL available through `--dart-define`

Useful command to inspect version info:

```bash
grep -n "version:" pubspec.yaml
```

## 4. Set up release signing

If you already have a release keystore, keep using it.

If you need to create one:

```bash
keytool -genkeypair -v \
  -keystore ~/rentalution-release.keystore \
  -alias rentalution \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

Then make sure Android release signing is wired up in:
- `rentalution_mobile/android/app/build.gradle.kts`

Notes:
- keep the keystore file and passwords somewhere safe
- do not lose the alias name or keystore password
- use the same signing key for future updates

## 5. Build the Play Store bundle

Google Play wants an Android App Bundle:

```bash
cd /home/neil/Projects/rentalution/rentalution_mobile
flutter build appbundle --release --dart-define=API_BASE_URL=https://your-production-domain/api/v1
```

The output is usually here:

```bash
ls -lh build/app/outputs/bundle/release/
```

You should see an `.aab` file.

## 6. Optional: inspect the bundle

You can sanity-check the generated bundle:

```bash
bundletool validate --bundle build/app/outputs/bundle/release/app-release.aab
```

If `bundletool` is not installed, you can skip this step.

## 7. Create or open the app in Play Console

Play Console URL:
- https://play.google.com/console

Common places you’ll visit inside Play Console:
- https://play.google.com/console/u/0/developers
- https://play.google.com/console/u/0/developers/your-app
- https://play.google.com/console/u/0/developers/your-app/app/dashboard

In the Play Console, set up:
- app name
- short description
- full description
- app icon
- feature graphic
- screenshots
- privacy policy URL
- support email
- category

## 8. Fill in release compliance sections

In Play Console, complete:
- Data safety
- Content rating
- Target audience
- App access
- Ads declaration
- News / financial / health / permissions declarations if relevant

If your app needs a privacy policy page, make sure the URL is live and public.

## 9. Upload the bundle

Usually you’ll start with internal testing first.

Typical Play Console sections:
- Internal testing
- Closed testing
- Production

Upload the `.aab` here:
- https://play.google.com/console/u/0/developers/your-app/testing/internal-testing

You can also browse to it from the Play Console dashboard.

Release notes example:

```text
Initial release of the Rentalution mobile app.
```

## 10. Test the Play build

Install the app from the testing track and verify:
- login
- browse categories
- browse products
- product detail pages
- images
- search
- any authenticated flows you use in production

If anything depends on production environment variables, make sure the bundle was built with the correct `--dart-define` values.

## 11. Promote to production

Once testing is clean:
- promote from internal testing to closed testing, or straight to production if appropriate
- choose a rollout percentage if you want a staged release

Production release section:
- https://play.google.com/console/u/0/developers/your-app/release/production

## 12. Update for future releases

For every new release:
- bump the app version/build number in `pubspec.yaml`
- rebuild the `.aab`
- upload a new release in Play Console
- keep the same signing key

Useful commands for the next release:

```bash
cd /home/neil/Projects/rentalution/rentalution_mobile
flutter pub get
flutter analyze
flutter build appbundle --release --dart-define=API_BASE_URL=https://your-production-domain/api/v1
```

## Suggested production checklist

- release keystore confirmed
- production API URL confirmed
- app icon and screenshots ready
- privacy policy live
- Data Safety form complete
- content rating complete
- bundle built successfully
- internal testing install verified

## Notes

- Build the app with the production backend URL, not the local emulator URL.
- Keep the Play signing key safe.
- The Play Console UI changes occasionally, but the core flow stays the same.
