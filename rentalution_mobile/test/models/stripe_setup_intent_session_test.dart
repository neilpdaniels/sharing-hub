import 'package:flutter_test/flutter_test.dart';
import 'package:rentalution_mobile/src/models/transaction_models.dart';

void main() {
  group('StripeSetupIntentSession.fromJson', () {
    test('parses expected fields', () {
      final session = StripeSetupIntentSession.fromJson({
        'provider': 'stripe',
        'setup_intent_id': 'seti_123',
        'client_secret': 'seti_123_secret',
      });

      expect(session.provider, 'stripe');
      expect(session.setupIntentId, 'seti_123');
      expect(session.clientSecret, 'seti_123_secret');
    });

    test('falls back to empty strings', () {
      final session = StripeSetupIntentSession.fromJson({});

      expect(session.provider, '');
      expect(session.setupIntentId, '');
      expect(session.clientSecret, '');
    });
  });
}
