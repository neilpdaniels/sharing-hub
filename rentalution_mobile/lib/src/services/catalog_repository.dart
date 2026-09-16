import 'dart:async';
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/catalog_models.dart';
import '../models/order_models.dart';
import 'api_client.dart';

class CatalogRepository {
  CatalogRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;
  final Map<String, Future<List<CategorySummary>>> _categoryCache = {};
  final Map<String, Future<List<ProductSummary>>> _productCache = {};
  final Map<String, Future<ProductDetail>> _productDetailCache = {};
  final Map<String, List<dynamic>> _categoryJson = {};
  final Map<String, String> _categoryEtags = {};
  final Map<String, DateTime> _categoryCheckedAt = {};
  final Set<String> _categoryRefreshing = {};
  static const Duration _categoryCheckInterval = Duration(minutes: 5);
  static const Duration _productCacheTtl = Duration(hours: 6);
  static const Duration _productDetailCacheTtl = Duration(hours: 6);

  Future<List<CategorySummary>> fetchCategories({String? parentSlug}) async {
    final parent = parentSlug?.trim();
    if (parent?.isNotEmpty == true && _categoryCache.containsKey('@all')) {
      final tree = await fetchAllCategories();
      return tree
          .where((category) => category.parentSlug == parent)
          .toList(growable: false);
    }
    return _fetchCategories(parentSlug: parent);
  }

  Future<List<CategorySummary>> fetchAllCategories() =>
      _fetchCategories(includeAll: true);

  Future<List<CategorySummary>> _fetchCategories({
    String? parentSlug,
    bool includeAll = false,
  }) async {
    final parent = parentSlug?.trim();
    final key = includeAll
        ? '@all'
        : parent?.isNotEmpty == true
        ? 'parent:$parent'
        : 'root';
    final cached = _categoryCache[key];
    if (cached != null) {
      // An in-flight initial load owns its request; refresh only resolved data.
      if (_categoryJson.containsKey(key)) {
        unawaited(_refreshCategories(key, parent));
      }
      return cached;
    }
    final future = _initialCategories(key, parent);
    _categoryCache[key] = future;
    try {
      return await future;
    } catch (_) {
      if (identical(_categoryCache[key], future)) _categoryCache.remove(key);
      rethrow;
    }
  }

  String _categoryStorageKey(String key) =>
      'catalog_categories_v2::${_apiClient.baseUrl}::$key';

  List<CategorySummary> _parseCategories(List<dynamic> json) => json
      .whereType<Map<String, dynamic>>()
      .map(CategorySummary.fromJson)
      .toList(growable: false);

  Future<List<CategorySummary>> _initialCategories(
    String key,
    String? parent,
  ) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getString(_categoryStorageKey(key));
      if (stored != null) {
        final envelope = jsonDecode(stored) as Map<String, dynamic>;
        final json = envelope['data'] as List<dynamic>;
        final categories = _parseCategories(json);
        _categoryJson[key] = json;
        if (envelope['etag'] is String) {
          _categoryEtags[key] = envelope['etag'] as String;
        }
        // Display even an older snapshot immediately, including when offline.
        unawaited(_refreshCategories(key, parent));
        return categories;
      }
    } catch (_) {
      // Corrupt/unavailable device storage must not prevent a network retry.
    }
    return _loadCategories(key, parent);
  }

  Future<List<ProductSummary>> fetchCategoryProducts({
    required String categorySlug,
    String? location,
    int? distanceKm,
    String? sortBy,
    Map<String, String>? attributeFilters,
    bool includeZeroListings = true,
  }) async {
    final cacheKey = [
      categorySlug.trim(),
      location?.trim() ?? '',
      distanceKm?.toString() ?? '',
      sortBy ?? '',
      includeZeroListings ? '1' : '0',
      if (attributeFilters != null)
        ...attributeFilters.entries
            .where((entry) => entry.value.trim().isNotEmpty)
            .map((entry) => '${entry.key}=${entry.value.trim()}'),
    ].join('|');
    final cached = _productCache[cacheKey];
    if (cached != null) {
      return cached;
    }

    final persisted = await _readCachedJsonList(
      _cacheStorageKey('products', cacheKey),
      ttl: _productCacheTtl,
    );
    if (persisted != null) {
      final cachedProducts = persisted
          .whereType<Map<String, dynamic>>()
          .map(ProductSummary.fromJson)
          .toList(growable: false);
      _productCache[cacheKey] = Future<List<ProductSummary>>.value(
        cachedProducts,
      );
      unawaited(
        _refreshCategoryProducts(
          cacheKey: cacheKey,
          categorySlug: categorySlug,
          location: location,
          distanceKm: distanceKm,
          sortBy: sortBy,
          attributeFilters: attributeFilters,
          includeZeroListings: includeZeroListings,
        ),
      );
      return _productCache[cacheKey]!;
    }

    final future = _loadCategoryProducts(
      cacheKey: cacheKey,
      categorySlug: categorySlug,
      location: location,
      distanceKm: distanceKm,
      sortBy: sortBy,
      attributeFilters: attributeFilters,
      includeZeroListings: includeZeroListings,
    );
    _productCache[cacheKey] = future;
    try {
      return await future;
    } catch (_) {
      // Do not replay a failed request when the caller retries.
      if (identical(_productCache[cacheKey], future)) {
        _productCache.remove(cacheKey);
      }
      rethrow;
    }
  }

  Future<ProductDetail> fetchProductDetail({
    required String productSlug,
    String? location,
    int? distanceKm,
    String? accessToken,
  }) async {
    final cacheKey = [
      productSlug.trim(),
      location?.trim() ?? '',
      distanceKm?.toString() ?? '',
    ].join('|');
    final cached = _productDetailCache[cacheKey];
    if (cached != null) {
      return cached;
    }

    final persisted = await _readCachedJsonObject(
      _cacheStorageKey('product_detail', cacheKey),
      ttl: _productDetailCacheTtl,
    );
    if (persisted != null) {
      final cachedDetail = ProductDetail.fromJson(persisted);
      _productDetailCache[cacheKey] = Future<ProductDetail>.value(cachedDetail);
      unawaited(
        _refreshProductDetail(
          cacheKey: cacheKey,
          productSlug: productSlug,
          location: location,
          distanceKm: distanceKm,
          accessToken: accessToken,
        ),
      );
      return _productDetailCache[cacheKey]!;
    }

    final future = _loadProductDetail(
      cacheKey: cacheKey,
      productSlug: productSlug,
      location: location,
      distanceKm: distanceKm,
      accessToken: accessToken,
    );
    _productDetailCache[cacheKey] = future;
    try {
      return await future;
    } catch (_) {
      // Do not replay a failed request when the caller retries.
      if (identical(_productDetailCache[cacheKey], future)) {
        _productDetailCache.remove(cacheKey);
      }
      rethrow;
    }
  }

  Future<List<CategorySummary>> _loadCategories(
    String cacheKey,
    String? parentSlug,
  ) async {
    final response = await _apiClient.getConditionalJsonList(
      '/categories/',
      etag: _categoryJson.containsKey(cacheKey)
          ? _categoryEtags[cacheKey]
          : null,
      queryParameters: cacheKey == '@all'
          ? {'include_top': 'true'}
          : parentSlug?.isNotEmpty == true
          ? {'parent_slug': parentSlug!}
          : null,
    );
    final json = response.data ?? _categoryJson[cacheKey]!;
    final categories = _parseCategories(json);
    _categoryJson[cacheKey] = json;
    if (response.etag != null) {
      _categoryEtags[cacheKey] = response.etag!;
    } else {
      _categoryEtags.remove(cacheKey);
    }
    _categoryCheckedAt[cacheKey] = DateTime.now();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _categoryStorageKey(cacheKey),
        jsonEncode({'etag': response.etag, 'data': json}),
      );
    } catch (_) {
      // Successful responses remain usable when device storage is unavailable.
    }
    return categories;
  }

  Future<void> _refreshCategories(String cacheKey, String? parentSlug) async {
    final checked = _categoryCheckedAt[cacheKey];
    if (_categoryRefreshing.contains(cacheKey) ||
        (checked != null &&
            DateTime.now().difference(checked) < _categoryCheckInterval)) {
      return;
    }
    _categoryRefreshing.add(cacheKey);
    _categoryCheckedAt[cacheKey] = DateTime.now();
    try {
      final categories = await _loadCategories(cacheKey, parentSlug);
      _categoryCache[cacheKey] = Future.value(categories);
    } catch (_) {
      // Keep displaying the last good snapshot when a refresh fails.
    } finally {
      _categoryRefreshing.remove(cacheKey);
    }
  }

  Future<List<ProductSummary>> _loadCategoryProducts({
    required String cacheKey,
    required String categorySlug,
    String? location,
    int? distanceKm,
    String? sortBy,
    Map<String, String>? attributeFilters,
    bool includeZeroListings = true,
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
    params['include_zero_listings'] = includeZeroListings ? 'true' : 'false';

    final json = await _apiClient.getJsonList(
      '/categories/$categorySlug/products/',
      queryParameters: params.isEmpty ? null : params,
    );
    await _writeCachedJsonList(_cacheStorageKey('products', cacheKey), json);
    return json
        .whereType<Map<String, dynamic>>()
        .map(ProductSummary.fromJson)
        .toList(growable: false);
  }

  Future<void> _refreshCategoryProducts({
    required String cacheKey,
    required String categorySlug,
    String? location,
    int? distanceKm,
    String? sortBy,
    Map<String, String>? attributeFilters,
    bool includeZeroListings = true,
  }) async {
    try {
      _productCache[cacheKey] = _loadCategoryProducts(
        cacheKey: cacheKey,
        categorySlug: categorySlug,
        location: location,
        distanceKm: distanceKm,
        sortBy: sortBy,
        attributeFilters: attributeFilters,
        includeZeroListings: includeZeroListings,
      );
      await _productCache[cacheKey];
    } catch (_) {
      _productCache.remove(cacheKey);
    }
  }

  Future<ProductDetail> _loadProductDetail({
    required String cacheKey,
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
    await _writeCachedJsonObject(
      _cacheStorageKey('product_detail', cacheKey),
      json,
    );
    return ProductDetail.fromJson(json);
  }

  Future<void> _refreshProductDetail({
    required String cacheKey,
    required String productSlug,
    String? location,
    int? distanceKm,
    String? accessToken,
  }) async {
    try {
      _productDetailCache[cacheKey] = _loadProductDetail(
        cacheKey: cacheKey,
        productSlug: productSlug,
        location: location,
        distanceKm: distanceKm,
        accessToken: accessToken,
      );
      await _productDetailCache[cacheKey];
    } catch (_) {
      _productDetailCache.remove(cacheKey);
    }
  }

  String _cacheStorageKey(String kind, String cacheKey) =>
      'catalog_cache::$kind::$cacheKey';

  Future<List<dynamic>?> _readCachedJsonList(
    String key, {
    required Duration ttl,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final payload = prefs.getString(key);
    if (payload == null || payload.isEmpty) {
      return null;
    }
    final decoded = jsonDecode(payload);
    if (decoded is! Map<String, dynamic>) {
      return null;
    }
    final cachedAt = DateTime.tryParse(decoded['cached_at']?.toString() ?? '');
    final data = decoded['data'];
    if (cachedAt == null || data is! List<dynamic>) {
      return null;
    }
    if (DateTime.now().difference(cachedAt) > ttl) {
      return null;
    }
    return data;
  }

  Future<Map<String, dynamic>?> _readCachedJsonObject(
    String key, {
    required Duration ttl,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final payload = prefs.getString(key);
    if (payload == null || payload.isEmpty) {
      return null;
    }
    final decoded = jsonDecode(payload);
    if (decoded is! Map<String, dynamic>) {
      return null;
    }
    final cachedAt = DateTime.tryParse(decoded['cached_at']?.toString() ?? '');
    final data = decoded['data'];
    if (cachedAt == null || data is! Map<String, dynamic>) {
      return null;
    }
    if (DateTime.now().difference(cachedAt) > ttl) {
      return null;
    }
    return data;
  }

  Future<void> _writeCachedJsonList(String key, List<dynamic> json) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      key,
      jsonEncode(<String, dynamic>{
        'cached_at': DateTime.now().toIso8601String(),
        'data': json,
      }),
    );
  }

  Future<void> _writeCachedJsonObject(
    String key,
    Map<String, dynamic> json,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      key,
      jsonEncode(<String, dynamic>{
        'cached_at': DateTime.now().toIso8601String(),
        'data': json,
      }),
    );
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
    bool includeZeroListings = true,
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
    params['include_zero_listings'] = includeZeroListings ? 'true' : 'false';

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
