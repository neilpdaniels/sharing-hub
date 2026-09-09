import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:rentalution_mobile/src/screens/transaction_detail_screen.dart';
import 'package:rentalution_mobile/src/services/api_client.dart';
import 'package:rentalution_mobile/src/services/friends_repository.dart';
import 'package:rentalution_mobile/src/services/transaction_repository.dart';

void main() {
  Future<void> showTransaction(
    WidgetTester tester, {
    required String status,
    required bool lender,
    required List<String> actions,
    String message = '',
    Map<String, dynamic> codes = const {},
    List<Map<String, dynamic>>? submitted,
  }) async {
    final api = ApiClient(
      baseUrl: 'https://example.test/api/v1',
      client: MockClient((request) async {
        if (request.method == 'POST') {
          submitted?.add(jsonDecode(request.body) as Map<String, dynamic>);
          return http.Response('{}', 200);
        }
        if (request.url.path.endsWith('/codes/')) {
          return http.Response(jsonEncode(codes), 200);
        }
        if (request.url.path.endsWith('/transactions/TEST/')) {
          return http.Response(
            jsonEncode({
              'transaction_reference': 'TEST',
              'transaction_status': status,
              'me_is_lender': lender,
              'me_is_renter': !lender,
              'deposit': 120,
              'deposit_card_setup_status': 'READY',
              'deposit_test_hold_status': 'SUCCESS',
              'workflow_payload': {
                'current_stage': 5,
                'message': message,
                'allowed_actions': actions,
              },
            }),
            200,
          );
        }
        return http.Response('[]', 200);
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: TransactionDetailScreen(
          transactionReference: 'TEST',
          accessToken: 'test',
          repository: TransactionRepository(apiClient: api),
          friendsRepository: FriendsRepository(apiClient: api),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> dispose(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox.shrink());
  }

  testWidgets(
    'agreed rental exposes lender collection evidence when server permits',
    (tester) async {
      await showTransaction(
        tester,
        status: 'RAGR',
        lender: true,
        actions: ['initiate_rental'],
      );
      expect(find.text('Submit Checkout Evidence'), findsOneWidget);
      expect(find.text('Agree With Lender Evidence'), findsNothing);
      await dispose(tester);
    },
  );

  testWidgets('borrower receives checkout code and can agree or counter', (
    tester,
  ) async {
    await showTransaction(
      tester,
      status: 'RDAYAWV',
      lender: false,
      actions: [
        'confirm_checkout_evidence',
        'submit_checkout_borrower_evidence',
      ],
      codes: {
        'checkout_code': {
          'pin': '123456',
          'qr_payload': 'SHARINGHUB:CHECKOUT_PIN:TEST:123456',
        },
      },
    );
    expect(find.text('Agree With Lender Evidence'), findsOneWidget);
    expect(find.text('Submit Counter-Evidence'), findsOneWidget);
    expect(find.text('PIN: 123456'), findsOneWidget);
    expect(find.text('Verify Collection & Start Rental'), findsNothing);
    await dispose(tester);
  });

  testWidgets('lender submits borrower collection PIN and has QR scanner', (
    tester,
  ) async {
    final submitted = <Map<String, dynamic>>[];
    await showTransaction(
      tester,
      status: 'RDAYAWV',
      lender: true,
      actions: ['verify_checkout_handover_pin'],
      submitted: submitted,
    );
    final pinField = find.widgetWithText(TextField, 'PIN');
    expect(pinField, findsOneWidget);
    expect(find.text('Scan QR Code'), findsOneWidget);
    expect(find.text('Show Collection QR / PIN'), findsNothing);
    await tester.ensureVisible(pinField);
    await tester.enterText(pinField, '123456');
    final verify = find.text('Verify Collection & Start Rental');
    await tester.ensureVisible(verify);
    await tester.tap(verify);
    await tester.pumpAndSettle();
    expect(submitted.single, {
      'action': 'verify_checkout_handover_pin',
      'pin': '123456',
    });
    await dispose(tester);
  });

  testWidgets(
    'ongoing rental uses server return availability and waiting message',
    (tester) async {
      const waiting = 'Rental commenced, awaiting return day on 12 Sep 2026.';
      await showTransaction(
        tester,
        status: 'RONG',
        lender: false,
        actions: [],
        message: waiting,
      );
      expect(find.text(waiting), findsOneWidget);
      expect(find.text('Submit / Update Return Evidence'), findsNothing);
      await dispose(tester);
      await showTransaction(
        tester,
        status: 'RONG',
        lender: false,
        actions: ['submit_return_borrower_evidence'],
      );
      expect(find.text('Submit / Update Return Evidence'), findsOneWidget);
      await dispose(tester);
    },
  );

  testWidgets('lender reviews return and presents code, borrower verifies', (
    tester,
  ) async {
    await showTransaction(
      tester,
      status: 'RRTDAYAWV',
      lender: true,
      actions: ['confirm_return_evidence', 'submit_lender_return_evidence'],
      codes: {
        'return_code': {
          'pin': '654321',
          'qr_payload': 'SHARINGHUB:RETURN_PIN:TEST:654321',
        },
      },
    );
    expect(find.text('Agree With Borrower Return Evidence'), findsOneWidget);
    expect(find.text('Submit Return Counter-Evidence'), findsOneWidget);
    expect(find.text('PIN: 654321'), findsOneWidget);
    expect(find.text('Verify Return & Continue'), findsNothing);
    await dispose(tester);
    await showTransaction(
      tester,
      status: 'RRTDAYAWV',
      lender: false,
      actions: ['verify_return_handover_pin'],
    );
    expect(find.text('Verify Return & Continue'), findsOneWidget);
    expect(find.text('Scan QR Code'), findsOneWidget);
    expect(find.text('Show Return QR / PIN'), findsNothing);
    await dispose(tester);
  });

  testWidgets(
    'deposit review waits for a proposal and exception actions follow server',
    (tester) async {
      await showTransaction(
        tester,
        status: 'RRTDPEND',
        lender: false,
        actions: [],
      );
      expect(find.text('Agree Deposit Return'), findsNothing);
      await dispose(tester);
      await showTransaction(
        tester,
        status: 'RRTDPEND',
        lender: false,
        actions: ['agree_deposit_return', 'contest_deposit_return'],
      );
      expect(find.text('Agree Deposit Return'), findsOneWidget);
      expect(find.text('Contest Deposit Return'), findsOneWidget);
      await dispose(tester);
      await showTransaction(
        tester,
        status: 'RDAYAWV',
        lender: false,
        actions: ['report_missing_rental'],
      );
      expect(find.text('Report Missing Rental'), findsOneWidget);
      await dispose(tester);
    },
  );
  testWidgets('polling unlocks return actions without a status change', (
    tester,
  ) async {
    final actions = <String>[];
    await showTransaction(
      tester,
      status: 'RONG',
      lender: false,
      actions: actions,
    );
    expect(find.text('Submit / Update Return Evidence'), findsNothing);
    actions.add('submit_return_borrower_evidence');
    await tester.pump(const Duration(seconds: 4));
    await tester.pumpAndSettle();
    expect(find.text('Submit / Update Return Evidence'), findsOneWidget);
    await dispose(tester);
  });
}
