import '../models/order_models.dart';
import 'api_client.dart';

class OrderRepository {
  OrderRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<OrderSummary>> fetchMyOrders({
    required String accessToken,
    String status = 'active',
  }) async {
    final json = await _apiClient.getJsonList(
      '/orders/mine/',
      accessToken: accessToken,
      queryParameters: {'status': status},
    );
    return json
        .whereType<Map<String, dynamic>>()
        .map(OrderSummary.fromJson)
        .toList(growable: false);
  }

  Future<OrderSummary> fetchOrderDetail({
    required String accessToken,
    required int orderId,
  }) async {
    final json = await _apiClient.getJsonObject(
      '/orders/$orderId/',
      accessToken: accessToken,
    );
    return OrderSummary.fromJson(json);
  }

  Future<OrderSummary> amendOrder({
    required String accessToken,
    required int orderId,
    required Map<String, dynamic> fields,
  }) async {
    final json = await _apiClient.patchJson(
      '/orders/$orderId/amend/',
      fields,
      accessToken: accessToken,
    );
    return OrderSummary.fromJson(json);
  }

  Future<void> cancelOrder({
    required String accessToken,
    required int orderId,
  }) async {
    await _apiClient.postJson(
      '/orders/$orderId/cancel/',
      const {},
      accessToken: accessToken,
    );
  }
}
