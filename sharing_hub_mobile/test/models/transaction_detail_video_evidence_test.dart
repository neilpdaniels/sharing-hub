import 'package:flutter_test/flutter_test.dart';
import 'package:sharing_hub_mobile/src/models/transaction_models.dart';

Map<String, dynamic> _detailJson({
  required String status,
  required bool meIsLender,
  required bool meIsRenter,
}) {
  return {
    'transaction_reference': 'TXN-1',
    'transaction_status': status,
    'payment_status': 'PEND',
    'deposit_status': 'PEND',
    'item_name': 'Camera',
    'counterparty_name': 'Alex',
    'parties_summary': 'Lender and renter',
    'price': 10,
    'friend_price': 10,
    'deposit': 50,
    'friend_deposit': 50,
    'quantity': 1,
    'me_is_lender': meIsLender,
    'me_is_renter': meIsRenter,
  };
}

void main() {
  group('TransactionDetail.canSubmitVideoEvidence', () {
    test('is true for lender in RAGR', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RAGR', meIsLender: true, meIsRenter: false),
      );

      expect(detail.canSubmitVideoEvidence, isTrue);
    });

    test('is true for renter in RDAYAWV', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RDAYAWV', meIsLender: false, meIsRenter: true),
      );

      expect(detail.canSubmitVideoEvidence, isTrue);
    });

    test('is true for renter in RONG', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RONG', meIsLender: false, meIsRenter: true),
      );

      expect(detail.canSubmitVideoEvidence, isTrue);
    });

    test('is true for renter in RRTDAYAWV', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RRTDAYAWV', meIsLender: false, meIsRenter: true),
      );

      expect(detail.canSubmitVideoEvidence, isTrue);
    });

    test('is true for lender in RRTDAYAWV', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RRTDAYAWV', meIsLender: true, meIsRenter: false),
      );

      expect(detail.canSubmitVideoEvidence, isTrue);
    });

    test('is false for lender in RDAYAWV', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RDAYAWV', meIsLender: true, meIsRenter: false),
      );

      expect(detail.canSubmitVideoEvidence, isFalse);
    });

    test('is false for renter in RAGR', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RAGR', meIsLender: false, meIsRenter: true),
      );

      expect(detail.canSubmitVideoEvidence, isFalse);
    });

    test('is false for unrelated status', () {
      final detail = TransactionDetail.fromJson(
        _detailJson(status: 'RENQ', meIsLender: true, meIsRenter: false),
      );

      expect(detail.canSubmitVideoEvidence, isFalse);
    });
  });
}
