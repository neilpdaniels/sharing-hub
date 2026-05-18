import '../models/catalog_models.dart';
import 'api_client.dart';

class CatalogRepository {
  CatalogRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<CategorySummary>> fetchCategories({
    String? parentSlug,
  }) async {
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
  }) async {
    final json = await _apiClient.getJsonObject('/products/$productSlug/');
    return ProductDetail.fromJson(json);
  }

  Future<List<ProductSummary>> searchProducts({
    required String query,
    String? location,
    String? categorySlug,
    int? distanceKm,
    String? sortBy,
  }) async {
    final params = <String, String>{
      'q': query,
    };

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

    final json = await _apiClient.getJsonList('/search/products/', queryParameters: params);
    return json
        .whereType<Map<String, dynamic>>()
        .map(ProductSummary.fromJson)
        .toList(growable: false);
  }
}
