class TransactionSummary {
  TransactionSummary({
    required this.reference,
    required this.status,
    required this.paymentStatus,
    required this.depositStatus,
    required this.itemName,
    required this.counterpartyName,
    required this.partiesSummary,
    required this.price,
    required this.friendPrice,
    required this.deposit,
    required this.friendDeposit,
    required this.quantity,
    required this.rentalStartDate,
    required this.rentalEndDate,
    required this.createdAt,
    required this.updatedAt,
  });

  final String reference;
  final String status;
  final String paymentStatus;
  final String depositStatus;
  final String itemName;
  final String counterpartyName;
  final String partiesSummary;
  final double price;
  final double friendPrice;
  final double deposit;
  final double friendDeposit;
  final int quantity;
  final DateTime? rentalStartDate;
  final DateTime? rentalEndDate;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  factory TransactionSummary.fromJson(Map<String, dynamic> json) {
    return TransactionSummary(
      reference: json['transaction_reference'] as String? ?? '',
      status: json['transaction_status'] as String? ?? '',
      paymentStatus: json['payment_status'] as String? ?? '',
      depositStatus: json['deposit_status'] as String? ?? '',
      itemName: json['item_name'] as String? ?? '',
      counterpartyName: json['counterparty_name'] as String? ?? '',
      partiesSummary: json['parties_summary'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      friendPrice: (json['friend_price'] as num?)?.toDouble() ?? 0,
      deposit: (json['deposit'] as num?)?.toDouble() ?? 0,
      friendDeposit: (json['friend_deposit'] as num?)?.toDouble() ?? 0,
      quantity: (json['quantity'] as num?)?.toInt() ?? 1,
      rentalStartDate: _parseDate(json['rental_start_date'] as String?),
      rentalEndDate: _parseDate(json['rental_end_date'] as String?),
      createdAt: _parseDate(json['created'] as String?),
      updatedAt: _parseDate(json['amended'] as String?),
    );
  }

  static DateTime? _parseDate(String? value) {
    if (value == null || value.isEmpty) {
      return null;
    }
    return DateTime.tryParse(value);
  }
}

class TransactionDetail extends TransactionSummary {
  TransactionDetail({
    required super.reference,
    required super.status,
    required super.paymentStatus,
    required super.depositStatus,
    required super.itemName,
    required super.counterpartyName,
    required super.partiesSummary,
    required super.price,
    required super.friendPrice,
    required super.deposit,
    required super.friendDeposit,
    required super.quantity,
    required super.rentalStartDate,
    required super.rentalEndDate,
    required super.createdAt,
    required super.updatedAt,
    required this.enquiryMessage,
    required this.orderPassiveDescription,
    required this.productStatus,
    required this.checkoutConditionVideoUrl,
    required this.checkoutBorrowerVideoUrl,
    required this.returnConditionVideoUrl,
    required this.returnBorrowerVideoUrl,
    required this.returnLenderVideoUrl,
    required this.checkoutHandoverVerifiedAt,
    required this.returnHandoverVerifiedAt,
    required this.lenderAgreedAt,
    required this.renterAgreedAt,
    required this.lenderAgreementPendingAt,
    required this.checkoutHandoverPinGeneratedAt,
    required this.returnHandoverPinGeneratedAt,
    required this.depositCardSetupStatus,
    required this.depositTestHoldStatus,
    required this.depositTestHoldAt,
    required this.depositCollectionStatus,
    required this.depositCollectionRequestedAt,
    required this.depositProposedReturnAmount,
    required this.depositProposedByLenderAt,
    required this.depositProposalContestedAt,
    required this.depositResolutionNotes,
    required this.listingImageUrl,
    required this.listingImageUrls,
    required this.meIsLender,
    required this.meIsRenter,
  });

  final String enquiryMessage;
  final String orderPassiveDescription;
  final String productStatus;
  final String checkoutConditionVideoUrl;
  final String checkoutBorrowerVideoUrl;
  final String returnConditionVideoUrl;
  final String returnBorrowerVideoUrl;
  final String returnLenderVideoUrl;
  final DateTime? checkoutHandoverVerifiedAt;
  final DateTime? returnHandoverVerifiedAt;
  final DateTime? lenderAgreedAt;
  final DateTime? renterAgreedAt;
  final DateTime? lenderAgreementPendingAt;
  final DateTime? checkoutHandoverPinGeneratedAt;
  final DateTime? returnHandoverPinGeneratedAt;
  final String depositCardSetupStatus;
  final String depositTestHoldStatus;
  final DateTime? depositTestHoldAt;
  final String depositCollectionStatus;
  final DateTime? depositCollectionRequestedAt;
  final double depositProposedReturnAmount;
  final DateTime? depositProposedByLenderAt;
  final DateTime? depositProposalContestedAt;
  final String depositResolutionNotes;
  final String listingImageUrl;
  final List<String> listingImageUrls;
  final bool meIsLender;
  final bool meIsRenter;

  factory TransactionDetail.fromJson(Map<String, dynamic> json) {
    return TransactionDetail(
      reference: json['transaction_reference'] as String? ?? '',
      status: json['transaction_status'] as String? ?? '',
      paymentStatus: json['payment_status'] as String? ?? '',
      depositStatus: json['deposit_status'] as String? ?? '',
      itemName: json['item_name'] as String? ?? '',
      counterpartyName: json['counterparty_name'] as String? ?? '',
      partiesSummary: json['parties_summary'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      friendPrice: (json['friend_price'] as num?)?.toDouble() ?? 0,
      deposit: (json['deposit'] as num?)?.toDouble() ?? 0,
      friendDeposit: (json['friend_deposit'] as num?)?.toDouble() ?? 0,
      quantity: (json['quantity'] as num?)?.toInt() ?? 1,
      rentalStartDate: TransactionSummary._parseDate(json['rental_start_date'] as String?),
      rentalEndDate: TransactionSummary._parseDate(json['rental_end_date'] as String?),
      createdAt: TransactionSummary._parseDate(json['created'] as String?),
      updatedAt: TransactionSummary._parseDate(json['amended'] as String?),
      enquiryMessage: json['enquiry_message'] as String? ?? '',
      orderPassiveDescription: json['order_passive_description'] as String? ?? '',
      productStatus: json['product_status'] as String? ?? '',
      checkoutConditionVideoUrl: json['checkout_condition_video_url'] as String? ?? '',
      checkoutBorrowerVideoUrl: json['checkout_borrower_video_url'] as String? ?? '',
      returnConditionVideoUrl: json['return_condition_video_url'] as String? ?? '',
      returnBorrowerVideoUrl: json['return_borrower_video_url'] as String? ?? '',
      returnLenderVideoUrl: json['return_lender_video_url'] as String? ?? '',
      checkoutHandoverVerifiedAt: TransactionSummary._parseDate(json['checkout_handover_verified_at'] as String?),
      returnHandoverVerifiedAt: TransactionSummary._parseDate(json['return_handover_verified_at'] as String?),
      lenderAgreedAt: TransactionSummary._parseDate(json['lender_agreed_at'] as String?),
      renterAgreedAt: TransactionSummary._parseDate(json['renter_agreed_at'] as String?),
      lenderAgreementPendingAt: TransactionSummary._parseDate(json['lender_agreement_pending_at'] as String?),
      checkoutHandoverPinGeneratedAt: TransactionSummary._parseDate(json['checkout_handover_pin_generated_at'] as String?),
      returnHandoverPinGeneratedAt: TransactionSummary._parseDate(json['return_handover_pin_generated_at'] as String?),
      depositCardSetupStatus: json['deposit_card_setup_status'] as String? ?? '',
      depositTestHoldStatus: json['deposit_test_hold_status'] as String? ?? '',
      depositTestHoldAt: TransactionSummary._parseDate(json['deposit_test_hold_at'] as String?),
      depositCollectionStatus: json['deposit_collection_status'] as String? ?? '',
      depositCollectionRequestedAt: TransactionSummary._parseDate(json['deposit_collection_requested_at'] as String?),
      depositProposedReturnAmount: (json['deposit_proposed_return_amount'] as num?)?.toDouble() ?? 0,
      depositProposedByLenderAt: TransactionSummary._parseDate(json['deposit_proposed_by_lender_at'] as String?),
      depositProposalContestedAt: TransactionSummary._parseDate(json['deposit_proposal_contested_at'] as String?),
      depositResolutionNotes: json['deposit_resolution_notes'] as String? ?? '',
      listingImageUrl: json['listing_image_url'] as String? ?? '',
      listingImageUrls: (json['listing_image_urls'] as List<dynamic>? ?? const [])
          .map((value) => value.toString())
          .where((value) => value.trim().isNotEmpty)
          .toList(growable: false),
      meIsLender: json['me_is_lender'] as bool? ?? false,
      meIsRenter: json['me_is_renter'] as bool? ?? false,
    );
  }
}

class TransactionMessageAttachment {
  TransactionMessageAttachment({
    required this.id,
    required this.imageUrl,
    required this.videoUrl,
    required this.uploadedAt,
  });

  final int id;
  final String imageUrl;
  final String videoUrl;
  final DateTime? uploadedAt;

  factory TransactionMessageAttachment.fromJson(Map<String, dynamic> json) {
    return TransactionMessageAttachment(
      id: json['id'] as int,
      imageUrl: json['image_url'] as String? ?? '',
      videoUrl: json['video_url'] as String? ?? '',
      uploadedAt: TransactionSummary._parseDate(json['uploaded_at'] as String?),
    );
  }
}

class TransactionMessage {
  TransactionMessage({
    required this.id,
    required this.userFromId,
    required this.userToId,
    required this.subject,
    required this.description,
    required this.created,
    required this.attachments,
  });

  final int id;
  final int userFromId;
  final int userToId;
  final String subject;
  final String description;
  final DateTime? created;
  final List<TransactionMessageAttachment> attachments;

  factory TransactionMessage.fromJson(Map<String, dynamic> json) {
    return TransactionMessage(
      id: json['id'] as int,
      userFromId: json['user_from_id'] as int,
      userToId: json['user_to_id'] as int,
      subject: json['subject'] as String? ?? '',
      description: json['description'] as String? ?? '',
      created: TransactionSummary._parseDate(json['created'] as String?),
      attachments: (json['attachments'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(TransactionMessageAttachment.fromJson)
          .toList(growable: false),
    );
  }
}

class InboxMessage {
  InboxMessage({
    required this.id,
    required this.transactionReference,
    required this.transactionStatus,
    required this.itemName,
    required this.counterpartyName,
    required this.direction,
    required this.unread,
    required this.subject,
    required this.description,
    required this.created,
    required this.attachments,
  });

  final int id;
  final String transactionReference;
  final String transactionStatus;
  final String itemName;
  final String counterpartyName;
  final String direction;
  final bool unread;
  final String subject;
  final String description;
  final DateTime? created;
  final List<TransactionMessageAttachment> attachments;

  factory InboxMessage.fromJson(Map<String, dynamic> json) {
    return InboxMessage(
      id: json['id'] as int,
      transactionReference: json['transaction_reference'] as String? ?? '',
      transactionStatus: json['transaction_status'] as String? ?? '',
      itemName: json['item_name'] as String? ?? '',
      counterpartyName: json['counterparty_name'] as String? ?? '',
      direction: json['direction'] as String? ?? 'sent',
      unread: json['unread'] as bool? ?? false,
      subject: json['subject'] as String? ?? '',
      description: json['description'] as String? ?? '',
      created: TransactionSummary._parseDate(json['created'] as String?),
      attachments: (json['attachments'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(TransactionMessageAttachment.fromJson)
          .toList(growable: false),
    );
  }
}

class TransactionCodes {
  TransactionCodes({
    required this.checkoutPin,
    required this.checkoutQrPayload,
    required this.returnPin,
    required this.returnQrPayload,
  });

  final String checkoutPin;
  final String checkoutQrPayload;
  final String returnPin;
  final String returnQrPayload;

  factory TransactionCodes.fromJson(Map<String, dynamic> json) {
    final checkout = json['checkout_code'] as Map<String, dynamic>?;
    final returned = json['return_code'] as Map<String, dynamic>?;
    return TransactionCodes(
      checkoutPin: checkout?['pin'] as String? ?? '',
      checkoutQrPayload: checkout?['qr_payload'] as String? ?? '',
      returnPin: returned?['pin'] as String? ?? '',
      returnQrPayload: returned?['qr_payload'] as String? ?? '',
    );
  }
}
