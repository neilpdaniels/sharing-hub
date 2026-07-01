import '../models/catalog_models.dart';
import '../models/order_models.dart';
import 'api_client.dart';

class CatalogRepository {
  CatalogRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<CategorySummary>> fetchCategories({String? parentSlug}) async {
    final params = <String, String>{};
    if (parentSlug != null && parentSlug.isNotEmpty) {
      params['parent_slug'] = parentSlug;
    }

    final json = await _apiClient.getJsonList(
      '/categories/',
      queryParameters: params.isEmpty ? null : params,
    );

    return json
        .whereType<Map<String, dynamic>>()
        .map(CategorySummary.fromJson)
        .toList(growable: false);
  }

  Future<List<ProductSummary>> fetchCategoryProducts({
    required String categorySlug,
    String? location,
    int? distanceKm,
    String? sortBy,
    Map<String, String>? attributeFilters,
    bool includeZeroListings = false,
  }) async {
    final params = <String, String>{};
    if (location != null && location.trim().isNotEmpty) {
      params['location'] = location.trim();
    }
    if (distanceKm != null) {
      params['distance'] = distanceKm.toString();
    }
    if (sortBy != null && sortBy.isNotEmpty) {
      params['sort_by'] = sortBy;
    }
    if (attributeFilters != null) {
      for (final entry in attributeFilters.entries) {
        final value = entry.value.trim();
        if (value.isNotEmpty) {
          params[entry.key] = value;
        }
      }
    }
    if (includeZeroListings) {
      params['include_zero_listings'] = 'true';
    }

    final json = await _apiClient.getJsonList(
      '/categories/$categorySlug/products/',
      queryParameters: params.isEmpty ? null : params,
    );

    return json
        .whereType<Map<String, dynamic>>()
        .map(ProductSummary.fromJson)
        .toList(growable: false);
  }

  Future<ProductDetail> fetchProductDetail({
    required String productSlug,
    String? location,
    int? distanceKm,
    String? accessToken,
  }) async {
    final params = <String, String>{};
    if (location != null && location.trim().isNotEmpty) {
      params['location'] = location.trim();
    }
    if (distanceKm != null) {
      params['distance'] = distanceKm.toString();
    }

    final json = await _apiClient.getJsonObject(
      '/products/$productSlug/',
      accessToken: accessToken,
      queryParameters: params.isEmpty ? null : params,
    );
    return ProductDetail.fromJson(json);
  }

  Future<List<OrderSummary>> fetchFavouriteOrders({
    required String accessToken,
  }) async {
    final json = await _apiClient.getJsonList(
      '/orders/favourites/',
      accessToken: accessToken,
    );
    return json
        .whereType<Map<String, dynamic>>()
        .map(OrderSummary.fromJson)
        .toList(growable: false);
  }

  Future<bool> toggleFavouriteOrder({
    required String accessToken,
    required int orderId,
  }) async {
    final json = await _apiClient.postJson(
      '/orders/$orderId/favourite/',
      const <String, dynamic>{},
      accessToken: accessToken,
    );
    return json['is_favourite'] as bool? ?? false;
  }

  Future<List<OrderSummary>> fetchLenderListings({
    required int lenderId,
  }) async {
    final json = await _apiClient.getJsonList('/lenders/$lenderId/listings/');
    return json
        .whereType<Map<String, dynamic>>()
        .map(OrderSummary.fromJson)
        .toList(growable: false);
  }

  Future<List<ProductSummary>> searchProducts({
    String? query,
    String? location,
    String? categorySlug,
    int? distanceKm,
    String? sortBy,
    Map<String, String>? attributeFilters,
    bool includeZeroListings = false,
  }) async {
    final params = <String, String>{};
    final trimmedQuery = query?.trim() ?? '';
    if (trimmedQuery.isNotEmpty) {
      params['q'] = trimmedQuery;
    }

    if (location != null && location.trim().isNotEmpty) {
      params['location'] = location.trim();
    }
    if (categorySlug != null && categorySlug.isNotEmpty) {
      params['category'] = categorySlug;
    }
    if (distanceKm != null) {
      params['distance'] = distanceKm.toString();
    }
    if (sortBy != null && sortBy.isNotEmpty) {
      params['sort_by'] = sortBy;
    }
    if (attributeFilters != null) {
      for (final entry in attributeFilters.entries) {
        final value = entry.value.trim();
        if (value.isNotEmpty) {
          params[entry.key] = value;
        }
      }
    }
    if (includeZeroListings) {
      params['include_zero_listings'] = 'true';
    }

    final json = await _apiClient.getJsonList(
      '/search/products/',
      queryParameters: params,
    );
    return json
        .whereType<Map<String, dynamic>>()
        .map(ProductSummary.fromJson)
        .toList(growable: false);
  }
}
