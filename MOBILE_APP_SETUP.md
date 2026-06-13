# Flutter + DRF Mobile Setup (Phase 1)

This setup provides:
- JWT login for mobile (`/api/v1/auth/login/`)
- Refresh token endpoint (`/api/v1/auth/refresh/`)
- Current user endpoint (`/api/v1/auth/me/`)
- Transaction list and detail endpoints (`/api/v1/transactions/`)
- Flutter mobile app scaffold with login and transaction list screens

## Backend Setup

### 1. Install Python dependencies
Use either the modern dependency flow (`pyproject.toml`) or requirements files.

### 2. Ensure Django uses the split settings package
For local runs:

```bash
export DJANGO_SETTINGS_MODULE=rentalution.settings.local
```

### 3. Run server

```bash
python manage.py runserver
```

## Mobile API Endpoints

Base path: `/api/v1/`

- `POST /api/v1/auth/login/`
  - body: `{ "login": "email-or-username", "password": "..." }`
  - returns: `access`, `refresh`, `user`, `profile`
- `POST /api/v1/auth/refresh/`
  - body: `{ "refresh": "..." }`
- `GET /api/v1/auth/me/`
  - auth: `Authorization: Bearer <access>`
- `GET /api/v1/transactions/`
  - auth required
- `GET /api/v1/transactions/<transaction_reference>/`
  - auth required
- `GET /api/v1/transactions/<transaction_reference>/messages/`
  - auth required
- `POST /api/v1/transactions/<transaction_reference>/messages/`
  - auth required
  - `JSON` payload: `{ "message_body": "..." }`
  - `multipart/form-data` for attachments:
    - `message_body`
    - `images` (repeatable)
    - `videos` (repeatable)
- `GET /api/v1/transactions/<transaction_reference>/codes/`
  - auth required
  - returns role-appropriate PIN + QR payload values when available
- `POST /api/v1/transactions/<transaction_reference>/actions/`
  - auth required
  - payload includes `action` plus action-specific fields

### Supported transaction actions

- `agree_rental`
- `reject_enquiry`
- `request_cancellation` (`reason`)
- `confirm_lender_contract`
- `reinitiate_lender_contract`
- `confirm_renter_contract`
- `reject_rental_agreement`
- `use_existing_card` (`payment_method_id`)
- `add_deposit_card` (`cardholder_name`, `card_brand`, `card_last4`)
- `confirm_stripe_card` (`payment_method_id`, `setup_intent_id`)
- `collect_deposit`
- `initiate_rental` (`checkout_video_url`, optional `payment_collected_placeholder`)
- `confirm_checkout_evidence`
- `submit_checkout_borrower_evidence` (`checkout_borrower_video_url`)
- `verify_checkout_handover_pin` (`pin` or `qr_payload`)
- `submit_return_borrower_evidence` (`return_video_url`)
- `confirm_return_evidence`
- `submit_lender_return_evidence` (`lender_return_video_url`)
- `verify_return_handover_pin` (`pin` or `qr_payload`)
- `propose_deposit_return` (`deposit_proposed_return_amount`, optional `deposit_resolution_notes`)
- `agree_deposit_return`
- `contest_deposit_return` (`deposit_resolution_notes`)
- `raise_deposit_dispute_admin` (`deposit_resolution_notes`)
- `secure_dispute_funds`
- `submit_feedback` (`communication_rating`, `delivery_return_rating`, `overall_rating`, optional `feedback_comment`)

## Flutter App Setup

Project path: `rentalution_mobile/`

### 1. Get dependencies

```bash
cd rentalution_mobile
flutter pub get
```

### 2. Run the app with API base URL

Android emulator local backend:

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
```

iOS simulator local backend:

```bash
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Physical device on same network (replace host):

```bash
flutter run --dart-define=API_BASE_URL=http://<your-lan-ip>:8000/api/v1
```

## Current Mobile App Flow

- App loads and attempts to restore stored tokens
- If no valid session, shows login screen
- On login success, stores JWT tokens and fetches transactions
- Home screen displays account summary + transaction list
- Pull-to-refresh and logout are implemented

## Next Step (Phase 2)

Build transaction action endpoints for app workflows:
- create enquiry
- send transaction messages
- transaction status transitions
- card setup/deposit integration endpoints
