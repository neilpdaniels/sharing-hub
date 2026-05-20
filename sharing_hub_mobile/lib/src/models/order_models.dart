class OrderSummary {
  OrderSummary({
    required this.id,
    required this.orderReference,
    required this.productId,
    required this.productName,
    required this.productSlug,
    required this.categorySlug,
    required this.listingImageUrl,
    required this.listingImageUrls,
    required this.direction,
    required this.status,
    required this.price,
    required this.currency,
    required this.description,
    required this.postcode,
    required this.latitude,
    required this.longitude,
    required this.letVisibility,
    required this.collectionPolicy,
    required this.deposit,
    required this.deliveryCost,
    required this.priceBands,
    required this.distanceKm,
    required this.maxRentalDays,
    required this.expiryDate,
    required this.amended,
    required this.blockedDates,
    required this.handoverUnavailableDates,
  });

  final int id;
  final String orderReference;
  final int productId;
  final String productName;
  final String productSlug;
  final String categorySlug;
  final String listingImageUrl;
  final List<String> listingImageUrls;
  final String direction;
  final String status;
  final double price;
  final String currency;
  final String description;
  final String postcode;
  final double? latitude;
  final double? longitude;
  final String letVisibility;
  final String collectionPolicy;
  final double deposit;
  final double deliveryCost;
  final List<LetPriceBandSummary> priceBands;
  final double? distanceKm;
  final int maxRentalDays;
  final DateTime? expiryDate;
  final DateTime? amended;
  final List<DateTime> blockedDates;
  final List<DateTime> handoverUnavailableDates;

  factory OrderSummary.fromJson(Map<String, dynamic> json) {
    return OrderSummary(
      id: json['id'] as int? ?? 0,
      orderReference: json['order_reference'] as String? ?? '',
      productId: json['product_id'] as int? ?? 0,
      productName: json['product_name'] as String? ?? '',
      productSlug: json['product_slug'] as String? ?? '',
      categorySlug: json['category_slug'] as String? ?? '',
      listingImageUrl: json['listing_image_url'] as String? ?? '',
      listingImageUrls:
          (json['listing_image_urls'] as List<dynamic>? ?? const [])
              .map((value) => value.toString())
              .toList(growable: false),
      direction: json['direction'] as String? ?? '',
      status: json['status'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      currency: json['currency'] as String? ?? 'GBP',
      description: json['description'] as String? ?? '',
      postcode: json['postcode'] as String? ?? '',
      latitude: _parseDouble(json['latitude']),
      longitude: _parseDouble(json['longitude']),
      letVisibility: json['let_visibility'] as String? ?? '',
      collectionPolicy: json['collection_policy'] as String? ?? '',
      deposit: (json['deposit'] as num?)?.toDouble() ?? 0,
      deliveryCost: (json['delivery_cost'] as num?)?.toDouble() ?? 0,
      priceBands: (json['price_bands'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(LetPriceBandSummary.fromJson)
          .toList(growable: false),
      distanceKm:
          _parseDouble(json['distance_km']) ??
          _parseDouble(json['nearest_distance_km']),
      maxRentalDays: json['max_rental_days'] as int? ?? 0,
      expiryDate: _parseDate(json['expiry_date'] as String?),
      amended: _parseDate(json['amended'] as String?),
      blockedDates: _parseDateList(
        json['blocked_dates'] as List<dynamic>? ?? const [],
      ),
      handoverUnavailableDates: _parseDateList(
        json['handover_unavailable_dates'] as List<dynamic>? ?? const [],
      ),
    );
  }

  static DateTime? _parseDate(String? value) {
    if (value == null || value.isEmpty) {
      return null;
    }
    return DateTime.tryParse(value);
  }

  static List<DateTime> _parseDateList(List<dynamic> values) {
    return values
        .map((value) => DateTime.tryParse(value.toString()))
        .whereType<DateTime>()
        .map((value) => DateTime.utc(value.year, value.month, value.day))
        .toList(growable: false);
  }

  static double? _parseDouble(dynamic value) {
    if (value == null) {
      return null;
    }
    if (value is num) {
      return value.toDouble();
    }
    return double.tryParse(value.toString());
  }
}

class LetPriceBandSummary {
  LetPriceBandSummary({required this.durationDays, required this.pricePerDay});

  final int durationDays;
  final double pricePerDay;

  factory LetPriceBandSummary.fromJson(Map<String, dynamic> json) {
    return LetPriceBandSummary(
      durationDays: json['duration_days'] as int? ?? 0,
      pricePerDay: (json['price_per_day'] as num?)?.toDouble() ?? 0,
    );
  }
}
