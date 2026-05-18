import 'dart:io';

import '../models/transaction_models.dart';
import 'api_client.dart';

class TransactionRepository {
  TransactionRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<TransactionSummary>> fetchTransactions({
    required String accessToken,
  }) async {
    final json = await _apiClient.getJsonList('/transactions/', accessToken: accessToken);
    return json
        .whereType<Map<String, dynamic>>()
        .map(TransactionSummary.fromJson)
        .toList(growable: false);
  }

  Future<List<InboxMessage>> fetchInbox({
    required String accessToken,
  }) async {
    final json = await _apiClient.getJsonList('/messages/inbox/', accessToken: accessToken);
    return json
        .whereType<Map<String, dynamic>>()
        .map(InboxMessage.fromJson)
        .toList(growable: false);
  }

  Future<TransactionDetail> createEnquiry({
    required String accessToken,
    required String orderReference,
    String? enquiryMessage,
    DateTime? rentalStartDate,
    DateTime? rentalEndDate,
  }) async {
    final payload = {
      'order_reference': orderReference,
      if (enquiryMessage != null && enquiryMessage.isNotEmpty)
        'enquiry_message': enquiryMessage,
      if (rentalStartDate != null) 'rental_start_date': _formatDate(rentalStartDate),
      if (rentalEndDate != null) 'rental_end_date': _formatDate(rentalEndDate),
    };
    final json = await _apiClient.postJson(
      '/transactions/',
      payload,
      accessToken: accessToken,
    );
    return TransactionDetail.fromJson(json);
  }

  String _formatDate(DateTime date) {
    final normalized = DateTime.utc(date.year, date.month, date.day);
    return normalized.toIso8601String().split('T').first;
  }

  Future<Map<String, dynamic>> performAction({
    required String accessToken,
    required String transactionReference,
    required String action,
    Map<String, dynamic> fields = const {},
  }) {
    return _apiClient.postJson(
      '/transactions/$transactionReference/actions/',
      {
        'action': action,
        ...fields,
      },
      accessToken: accessToken,
    );
  }

  Future<TransactionDetail> fetchTransactionDetail({
    required String accessToken,
    required String transactionReference,
  }) async {
    final json = await _apiClient.getJsonObject(
      '/transactions/$transactionReference/',
      accessToken: accessToken,
    );
    return TransactionDetail.fromJson(json);
  }

  Future<TransactionCodes> fetchCodes({
    required String accessToken,
    required String transactionReference,
  }) async {
    final json = await _apiClient.getJsonObject(
      '/transactions/$transactionReference/codes/',
      accessToken: accessToken,
    );
    return TransactionCodes.fromJson(json);
  }

  Future<List<TransactionMessage>> fetchMessages({
    required String accessToken,
    required String transactionReference,
  }) async {
    final json = await _apiClient.getJsonList(
      '/transactions/$transactionReference/messages/',
      accessToken: accessToken,
    );
    return json
        .whereType<Map<String, dynamic>>()
        .map(TransactionMessage.fromJson)
        .toList(growable: false);
  }

  Future<TransactionMessage> sendTextMessage({
    required String accessToken,
    required String transactionReference,
    required String messageBody,
  }) async {
    final json = await _apiClient.postJson(
      '/transactions/$transactionReference/messages/',
      {'message_body': messageBody},
      accessToken: accessToken,
    );
    return TransactionMessage.fromJson(json);
  }

  Future<TransactionMessage> sendMessageWithAttachments({
    required String accessToken,
    required String transactionReference,
    required String messageBody,
    List<File> imageFiles = const [],
    List<File> videoFiles = const [],
  }) async {
    final json = await _apiClient.postMultipart(
      '/transactions/$transactionReference/messages/',
      accessToken: accessToken,
      fields: {'message_body': messageBody},
      imageFiles: imageFiles,
      videoFiles: videoFiles,
    );
    return TransactionMessage.fromJson(json);
  }
}
