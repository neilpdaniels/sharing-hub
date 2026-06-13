import 'order_models.dart';

String _asString(dynamic value) {
  if (value == null) {
    return '';
  }
  return value.toString();
}

class CategorySummary {
  CategorySummary({
    required this.id,
    required this.title,
    required this.slug,
    required this.parentSlug,
    required this.description,
    required this.imageUrl,
  });

  final int id;
  final String title;
  final String slug;
  final String parentSlug;
  final String description;
  final String imageUrl;

  factory CategorySummary.fromJson(Map<String, dynamic> json) {
    return CategorySummary(
      id: json['id'] as int? ?? 0,
      title: _asString(json['title']),
      slug: _asString(json['slug']),
      parentSlug: _asString(json['parent_slug']),
      description: _asString(json['description']),
      imageUrl: _asString(json['image_url']),
    );
  }
}

class ProductSummary {
  ProductSummary({
    required this.id,
    required this.name,
    required this.shortName,
    required this.slug,
    required this.description,
    required this.categorySlug,
    required this.categoryTitle,
    required this.categoryDescription,
    required String? imageUrl,
    required this.tags,
    required this.attributeOneValue,
    required this.attributeTwoValue,
    required this.attributeThreeValue,
    required this.attributeFourValue,
    required this.attributeFiveValue,
    required this.riskRating,
    required this.nearestDistanceKm,
    required this.activeOrderCount,
  }) : _imageUrl = imageUrl;

  final int id;
  final String name;
  final String shortName;
  final String slug;
  final String description;
  final String categorySlug;
  final String categoryTitle;
  final String categoryDescription;
  final String? _imageUrl;
  String get imageUrl => _imageUrl ?? '';
  final List<String> tags;
  final String attributeOneValue;
  final String attributeTwoValue;
  final String attributeThreeValue;
  final String attributeFourValue;
  final String attributeFiveValue;
  final int riskRating;
  final double? nearestDistanceKm;
  final int activeOrderCount;

  factory ProductSummary.fromJson(Map<String, dynamic> json) {
    return ProductSummary(
      id: json['id'] as int? ?? 0,
      name: _asString(json['name']),
      shortName: _asString(json['short_name']),
      slug: _asString(json['slug']),
      description: _asString(json['description']),
      categorySlug: _asString(json['category_slug']),
      categoryTitle: _asString(json['category_title']),
      categoryDescription: _asString(json['category_description']),
      imageUrl: _asString(json['image_url']),
      tags: (json['tags'] as List<dynamic>? ?? const []).map((e) => e.toString()).toList(growable: false),
      attributeOneValue: _asString(json['attribute_one_value']),
      attributeTwoValue: _asString(json['attribute_two_value']),
      attributeThreeValue: _asString(json['attribute_three_value']),
      attributeFourValue: _asString(json['attribute_four_value']),
      attributeFiveValue: _asString(json['attribute_five_value']),
      riskRating: (json['risk_rating'] as num?)?.toInt() ?? 0,
      nearestDistanceKm: (json['nearest_distance_km'] as num?)?.toDouble(),
      activeOrderCount: json['active_order_count'] as int? ?? 0,
    );
  }
}

class ProductDetail extends ProductSummary {
  ProductDetail({
    required super.id,
    required super.name,
    required super.shortName,
    required super.slug,
    required super.description,
    required super.categorySlug,
    required super.categoryTitle,
    required super.categoryDescription,
    required super.imageUrl,
    required super.tags,
    required super.attributeOneValue,
    required super.attributeTwoValue,
    required super.attributeThreeValue,
    required super.attributeFourValue,
    required super.attributeFiveValue,
    required super.riskRating,
    required super.nearestDistanceKm,
    required super.activeOrderCount,
    required this.activeOrders,
  });

  final List<OrderSummary> activeOrders;

  factory ProductDetail.fromJson(Map<String, dynamic> json) {
    return ProductDetail(
      id: json['id'] as int? ?? 0,
      name: _asString(json['name']),
      shortName: _asString(json['short_name']),
      slug: _asString(json['slug']),
      description: _asString(json['description']),
      categorySlug: _asString(json['category_slug']),
      categoryTitle: _asString(json['category_title']),
      categoryDescription: _asString(json['category_description']),
      imageUrl: _asString(json['image_url']),
      tags: (json['tags'] as List<dynamic>? ?? const []).map((e) => e.toString()).toList(growable: false),
      attributeOneValue: _asString(json['attribute_one_value']),
      attributeTwoValue: _asString(json['attribute_two_value']),
      attributeThreeValue: _asString(json['attribute_three_value']),
      attributeFourValue: _asString(json['attribute_four_value']),
      attributeFiveValue: _asString(json['attribute_five_value']),
      riskRating: (json['risk_rating'] as num?)?.toInt() ?? 0,
      nearestDistanceKm: (json['nearest_distance_km'] as num?)?.toDouble(),
      activeOrderCount: json['active_order_count'] as int? ?? 0,
      activeOrders: (json['active_orders'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(OrderSummary.fromJson)
          .toList(growable: false),
    );
  }
}
