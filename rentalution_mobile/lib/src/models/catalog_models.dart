import 'order_models.dart';

String _asString(dynamic value) {
  if (value == null) {
    return '';
  }
  return value.toString();
}

String _plainTextDescription(dynamic value) {
  final text = _asString(value);
  if (text.isEmpty) {
    return '';
  }

  return text
      .replaceAll(RegExp(r'<br\s*/?>', caseSensitive: false), ' ')
      .replaceAll(RegExp(r'<[^>]+>'), ' ')
      .replaceAll(RegExp(r'&nbsp;', caseSensitive: false), ' ')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
}

class CategoryAttributeDefinition {
  CategoryAttributeDefinition({
    required this.order,
    required this.name,
    required this.valueSource,
    required this.sortable,
    required this.filterable,
    required this.defaultFilteredValue,
    required this.allowedValues,
    required this.fieldName,
    required this.queryParam,
    required this.sortKeyAsc,
    required this.sortKeyDesc,
    required this.inputType,
  });

  final int order;
  final String name;
  final String valueSource;
  final bool sortable;
  final bool filterable;
  final String defaultFilteredValue;
  final List<String> allowedValues;
  final String fieldName;
  final String queryParam;
  final String sortKeyAsc;
  final String sortKeyDesc;
  final String inputType;

  factory CategoryAttributeDefinition.fromJson(Map<String, dynamic> json) {
    return CategoryAttributeDefinition(
      order: (json['order'] as num?)?.toInt() ?? 0,
      name: _asString(json['name']),
      valueSource: _asString(json['value_source']),
      sortable: json['sortable'] as bool? ?? false,
      filterable: json['filterable'] as bool? ?? false,
      defaultFilteredValue: _asString(json['default_filtered_value']),
      allowedValues: (json['allowed_values'] as List<dynamic>? ?? const [])
          .map((value) => value.toString())
          .toList(growable: false),
      fieldName: _asString(json['field_name']),
      queryParam: _asString(json['query_param']),
      sortKeyAsc: _asString(json['sort_key_asc']),
      sortKeyDesc: _asString(json['sort_key_desc']),
      inputType: _asString(json['input_type']),
    );
  }
}

class ProductAttributeValue {
  ProductAttributeValue({
    required this.order,
    required this.name,
    required this.value,
    required this.valueSource,
    required this.filterable,
    required this.sortable,
    required this.allowedValues,
  });

  final int order;
  final String name;
  final String value;
  final String valueSource;
  final bool filterable;
  final bool sortable;
  final List<String> allowedValues;

  factory ProductAttributeValue.fromJson(Map<String, dynamic> json) {
    return ProductAttributeValue(
      order: (json['order'] as num?)?.toInt() ?? 0,
      name: _asString(json['name']),
      value: _asString(json['value']),
      valueSource: _asString(json['value_source']),
      filterable: json['filterable'] as bool? ?? false,
      sortable: json['sortable'] as bool? ?? false,
      allowedValues: (json['allowed_values'] as List<dynamic>? ?? const [])
          .map((value) => value.toString())
          .toList(growable: false),
    );
  }
}

class CategorySummary {
  CategorySummary({
    required this.id,
    required this.title,
    required this.slug,
    required this.parentSlug,
    required this.description,
    required this.imageUrl,
    required this.thumbnailUrl,
    required this.attributeDefinitions,
  });

  final int id;
  final String title;
  final String slug;
  final String parentSlug;
  final String description;
  final String imageUrl;
  final String thumbnailUrl;
  final List<CategoryAttributeDefinition> attributeDefinitions;

  factory CategorySummary.fromJson(Map<String, dynamic> json) {
    return CategorySummary(
      id: json['id'] as int? ?? 0,
      title: _asString(json['title']),
      slug: _asString(json['slug']),
      parentSlug: _asString(json['parent_slug']),
      description: _plainTextDescription(json['description']),
      imageUrl: _asString(json['image_url']),
      thumbnailUrl: _asString(json['thumbnail_url']),
      attributeDefinitions:
          (json['attribute_definitions'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .map(CategoryAttributeDefinition.fromJson)
              .toList(growable: false),
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
    required String? thumbnailUrl,
    required this.tags,
    required this.attributeOneValue,
    required this.attributeTwoValue,
    required this.attributeThreeValue,
    required this.attributeFourValue,
    required this.attributeFiveValue,
    required this.attributeDefinitions,
    required this.attributes,
    required this.riskRating,
    required this.nearestDistanceKm,
    required this.activeOrderCount,
  }) : _imageUrl = imageUrl,
       _thumbnailUrl = thumbnailUrl;

  final int id;
  final String name;
  final String shortName;
  final String slug;
  final String description;
  final String categorySlug;
  final String categoryTitle;
  final String categoryDescription;
  final String? _imageUrl;
  final String? _thumbnailUrl;
  String get imageUrl => _imageUrl ?? '';
  String get thumbnailUrl => _thumbnailUrl ?? '';
  final List<String> tags;
  final String attributeOneValue;
  final String attributeTwoValue;
  final String attributeThreeValue;
  final String attributeFourValue;
  final String attributeFiveValue;
  final List<CategoryAttributeDefinition> attributeDefinitions;
  final List<ProductAttributeValue> attributes;
  final int riskRating;
  final double? nearestDistanceKm;
  final int activeOrderCount;

  factory ProductSummary.fromJson(Map<String, dynamic> json) {
    return ProductSummary(
      id: json['id'] as int? ?? 0,
      name: _asString(json['name']),
      shortName: _asString(json['short_name']),
      slug: _asString(json['slug']),
      description: _plainTextDescription(json['description']),
      categorySlug: _asString(json['category_slug']),
      categoryTitle: _asString(json['category_title']),
      categoryDescription: _plainTextDescription(json['category_description']),
      imageUrl: _asString(json['image_url']),
      thumbnailUrl: _asString(json['thumbnail_url']),
      tags: (json['tags'] as List<dynamic>? ?? const []).map((e) => e.toString()).toList(growable: false),
      attributeOneValue: _asString(json['attribute_one_value']),
      attributeTwoValue: _asString(json['attribute_two_value']),
      attributeThreeValue: _asString(json['attribute_three_value']),
      attributeFourValue: _asString(json['attribute_four_value']),
      attributeFiveValue: _asString(json['attribute_five_value']),
      attributeDefinitions:
          (json['attribute_definitions'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .map(CategoryAttributeDefinition.fromJson)
              .toList(growable: false),
      attributes: (json['attributes'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ProductAttributeValue.fromJson)
          .toList(growable: false),
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
    required super.thumbnailUrl,
    required super.tags,
    required super.attributeOneValue,
    required super.attributeTwoValue,
    required super.attributeThreeValue,
    required super.attributeFourValue,
    required super.attributeFiveValue,
    required super.attributeDefinitions,
    required super.attributes,
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
      description: _plainTextDescription(json['description']),
      categorySlug: _asString(json['category_slug']),
      categoryTitle: _asString(json['category_title']),
      categoryDescription: _plainTextDescription(json['category_description']),
      imageUrl: _asString(json['image_url']),
      thumbnailUrl: _asString(json['thumbnail_url']),
      tags: (json['tags'] as List<dynamic>? ?? const []).map((e) => e.toString()).toList(growable: false),
      attributeOneValue: _asString(json['attribute_one_value']),
      attributeTwoValue: _asString(json['attribute_two_value']),
      attributeThreeValue: _asString(json['attribute_three_value']),
      attributeFourValue: _asString(json['attribute_four_value']),
      attributeFiveValue: _asString(json['attribute_five_value']),
      attributeDefinitions:
          (json['attribute_definitions'] as List<dynamic>? ?? const [])
              .whereType<Map<String, dynamic>>()
              .map(CategoryAttributeDefinition.fromJson)
              .toList(growable: false),
      attributes: (json['attributes'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ProductAttributeValue.fromJson)
          .toList(growable: false),
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
