# Social sign-in implementation plan

## Goal

Offer password-free sign-up/sign-in without weakening Rentalution's existing safety gates. Initial providers are Google and Sign in with Apple. Facebook is a later provider using the same account-linking model.

## Account and verification policy

1. A provider token proves only the provider identity; it does not verify a Rentalution address or mobile number.
2. The first provider sign-in creates or links a Rentalution user and records the immutable provider subject identifier.
3. Google verified email / Apple verified or relay email can satisfy Rentalution email confirmation.
4. The member then completes date of birth, UK mobile number and address. Mobile verification remains a Twilio Verify OTP; address verification remains the existing address/KYC flow.
5. Browsing is permitted before completion. Transactions, lending and sensitive collection information remain gated by the existing `email_confirmed`, `mobile_verified` and `address_verified` checks.
6. Never link an existing account by email alone without an authenticated, explicit account-linking flow. This prevents account takeover where a provider reuses or changes an address.

## Delivery phases

### Phase 1 — backend identity foundation

- [x] Add `SocialIdentity` with a unique `(provider, provider_subject)` key.
- [x] Add a Google ID-token exchange endpoint which validates issuer, signature, audience, expiry and verified-email claim server-side.
- [x] Issue the existing Rentalution JWTs and return explicit onboarding status.
- [x] Add provider credentials to deployment configuration, not mobile binaries: `GOOGLE_OAUTH_MOBILE_CLIENT_IDS` is a comma-separated allow-list of Android and iOS OAuth client IDs.
- [x] Add onboarding API endpoints to collect date of birth, UK mobile and address, and to send/check the existing Twilio Verify code.
- [x] Add tests covering new social users, safe refusal to auto-link an existing email account, and resetting verification if a phone/address changes.
- [ ] Add tests for rejected token expiry and a concurrent duplicate identity.

### Phase 2 — Google mobile and web UX

- [ ] Add native Google sign-in to Android/iOS Flutter with platform-specific OAuth client IDs.
- [ ] Send only the resulting ID token to the server; the server owns verification and account creation.
- [ ] Add a Google button to the website login/register pages with PKCE/server callback support.

### Phase 3 — finish-profile and verification UX

- [ ] Add a post-provider onboarding screen for date of birth, mobile and address.
- [x] Add mobile API endpoints for Twilio Verify send/check; reuse the existing account verification service.
- [ ] Reuse address lookup and show a clear “what remains” checklist.
- [ ] Block transaction/lending actions until verification is complete.

### Phase 4 — Sign in with Apple

- [ ] Configure the Apple App ID capability, Services ID (web), redirect URI and private key in Apple Developer.
- [ ] Verify Apple identity tokens against Apple's JWKS and issuer/audience rules.
- [ ] Handle relay email and Apple's first-authorisation-only name response.
- [ ] Offer Apple alongside Google on iOS and web; this meets App Review Guideline 4.8 when third-party primary login is offered.

### Phase 5 — account safety and pilot

- [ ] Account settings: link/unlink provider with password or a second provider required before removing the last sign-in method.
- [ ] Test existing-account linking, duplicate email, cancelled provider flow, revoked provider access and relay-email delivery.
- [ ] Update privacy policy/data declarations and App Review notes.
- [ ] Pilot Google + Apple first; evaluate Facebook only after uptake evidence.

## Implemented API contract

All endpoints below are under `/api/v1/` (subject to the existing project API prefix).

- `POST auth/social/google/` accepts `{ "id_token": "..." }`. It returns the normal JWT session payload plus `onboarding_required`. It never auto-links by email; an existing email returns HTTP 409 and `account_link_required: true`.
- `POST auth/onboarding/profile/` requires the returned bearer token and accepts the member's date of birth, UK mobile number and address. It creates the missing profile or updates it. A changed phone resets mobile verification; a changed address resets baseline/Stripe identity verification.
- `POST auth/onboarding/mobile/send/` requires the bearer token and sends the Twilio Verify SMS.
- `POST auth/onboarding/mobile/check/` requires the bearer token and `{ "code": "..." }`; an approved code marks the mobile number verified.

Address verification is deliberately not granted by Google. The existing Stripe Identity KYC route remains the authoritative route when address/identity proof is required.
