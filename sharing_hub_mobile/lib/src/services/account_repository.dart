import '../models/account_models.dart';
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
}
