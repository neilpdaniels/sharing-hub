import '../models/account_models.dart';
import '../models/transaction_models.dart';
import 'api_client.dart';

class AccountRepository {
  AccountRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<AccountDetails> fetchAccountDetails({required String accessToken}) async {
    final json = await _apiClient.getJsonObject(
      '/account/me/',
      accessToken: accessToken,
    );
    return AccountDetails.fromJson(json);
  }

  Future<KycStatus> fetchKycStatus({required String accessToken}) async {
    final json = await _apiClient.getJsonObject(
      '/account/kyc-status/',
      accessToken: accessToken,
    );
    return KycStatus.fromJson(json);
  }

  Future<AccountDetails> amendAccount({
    required String accessToken,
    required Map<String, dynamic> fields,
  }) async {
    final json = await _apiClient.patchJson(
      '/account/me/',
      fields,
      accessToken: accessToken,
    );
    return AccountDetails.fromJson(json);
  }

  Future<List<PaymentMethodSummary>> fetchPaymentMethods({required String accessToken}) async {
    final json = await _apiClient.getJsonList(
      '/payment-methods/',
      accessToken: accessToken,
    );

    return json
        .whereType<Map<String, dynamic>>()
        .map(PaymentMethodSummary.fromJson)
        .toList(growable: false);
  }

  Future<void> setDefaultPaymentMethod({
    required String accessToken,
    required int paymentMethodId,
  }) async {
    await _apiClient.postJson(
      '/payment-methods/$paymentMethodId/set-default/',
      const {},
      accessToken: accessToken,
    );
  }

  Future<void> deletePaymentMethod({
    required String accessToken,
    required int paymentMethodId,
  }) async {
    await _apiClient.postJson(
      '/payment-methods/$paymentMethodId/delete/',
      const {},
      accessToken: accessToken,
    );
  }

  Future<StripeSetupIntentSession> createPaymentMethodSetupIntent({
    required String accessToken,
  }) async {
    final json = await _apiClient.postJson(
      '/payment-methods/setup-intent/',
      const {},
      accessToken: accessToken,
    );
    return StripeSetupIntentSession.fromJson(json);
  }

  Future<PaymentMethodSummary> confirmPaymentMethodSetup({
    required String accessToken,
    required String setupIntentId,
    required String paymentMethodId,
  }) async {
    final json = await _apiClient.postJson(
      '/payment-methods/confirm/',
      {
        'setup_intent_id': setupIntentId,
        'payment_method_id': paymentMethodId,
      },
      accessToken: accessToken,
    );
    return PaymentMethodSummary(
      id: 0,
      cardBrand: json['card_brand'] as String? ?? 'Card',
      cardFunding: json['card_funding'] as String? ?? '',
      cardLast4: json['card_last4'] as String? ?? '',
      isDefault: false,
    );
  }

  Future<String> fetchStripePublishableKey({
    required String accessToken,
  }) async {
    final json = await _apiClient.getJsonObject(
      '/config/',
      accessToken: accessToken,
    );
    return json['stripe_publishable_key'] as String? ?? '';
  }
}
