# Firebase Environment Layout

Android:
- Dev config: `android/app/src/dev/google-services.json`
- Prod config: `android/app/src/prod/google-services.json`

iOS:
- Dev config: `ios/Firebase/dev/GoogleService-Info.plist`
- Prod config: `ios/Firebase/prod/GoogleService-Info.plist`

Android flavors:
- `dev` uses the dev `google-services.json`
- `prod` uses the prod `google-services.json`

Notes:
- Keep the dev files in place and replace the placeholder prod files with the real production Firebase downloads.
- The iOS app still needs the chosen plist copied into the app bundle before build. The file split above gives you a clean place to store each environment's plist.
