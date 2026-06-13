class AccountDetails {
  AccountDetails({
    required this.username,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.mobileNumber,
    required this.addressLine1,
    required this.addressLine2,
    required this.town,
    required this.county,
    required this.postcode,
  });

  final String username;
  final String email;
  final String firstName;
  final String lastName;
  final String mobileNumber;
  final String addressLine1;
  final String addressLine2;
  final String town;
  final String county;
  final String postcode;

  factory AccountDetails.fromJson(Map<String, dynamic> json) {
    final user = (json['user'] as Map<String, dynamic>? ?? const {});
    final profile = (json['profile'] as Map<String, dynamic>? ?? const {});

    return AccountDetails(
      username: user['username'] as String? ?? '',
      email: user['email'] as String? ?? '',
      firstName: user['first_name'] as String? ?? '',
      lastName: user['last_name'] as String? ?? '',
      mobileNumber: profile['mobile_number'] as String? ?? '',
      addressLine1: profile['address_line_1'] as String? ?? '',
      addressLine2: profile['address_line_2'] as String? ?? '',
      town: profile['town'] as String? ?? '',
      county: profile['county'] as String? ?? '',
      postcode: profile['postcode'] as String? ?? '',
    );
  }
}

class PaymentMethodSummary {
  PaymentMethodSummary({
    required this.id,
    required this.cardBrand,
    required this.cardFunding,
    required this.cardLast4,
    required this.isDefault,
  });

  final int id;
  final String cardBrand;
  final String cardFunding;
  final String cardLast4;
  final bool isDefault;

  factory PaymentMethodSummary.fromJson(Map<String, dynamic> json) {
    return PaymentMethodSummary(
      id: json['id'] as int? ?? 0,
      cardBrand: json['card_brand'] as String? ?? 'Card',
      cardFunding: json['card_funding'] as String? ?? '',
      cardLast4: json['card_last4'] as String? ?? '',
      isDefault: json['is_default'] as bool? ?? false,
    );
  }
}

class KycStatus {
  KycStatus({
    required this.isVerified,
    required this.baselineVerified,
    required this.emailConfirmed,
    required this.mobileVerified,
    required this.addressVerified,
    required this.statusLabel,
    required this.webUrl,
    required this.verifiedAt,
  });

  final bool isVerified;
  final bool baselineVerified;
  final bool emailConfirmed;
  final bool mobileVerified;
  final bool addressVerified;
  final String statusLabel;
  final String webUrl;
  final String? verifiedAt;

  factory KycStatus.fromJson(Map<String, dynamic> json) {
    return KycStatus(
      isVerified: json['is_verified'] as bool? ?? false,
      baselineVerified: json['baseline_verified'] as bool? ?? false,
      emailConfirmed: json['email_confirmed'] as bool? ?? false,
      mobileVerified: json['mobile_verified'] as bool? ?? false,
      addressVerified: json['address_verified'] as bool? ?? false,
      statusLabel: json['status_label'] as String? ?? 'Verification pending',
      webUrl: json['web_url'] as String? ?? '',
      verifiedAt: json['verified_at']?.toString(),
    );
  }
}
