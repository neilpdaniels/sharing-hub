import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
    String overdueKind = '',
    String depositNotes = '',
    List<Map<String, dynamic>> evidence = const [],
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
              'workflow_stage': status == 'RRTDAYAWV' ? 6 : 5,
              'me_is_lender': lender,
              'me_is_renter': !lender,
              'deposit': 120,
              'deposit_resolution_notes': depositNotes,
              'evidence_items': evidence,
              'deposit_card_setup_status': 'READY',
              'deposit_test_hold_status': 'SUCCESS',
              'workflow_payload': {
                'current_stage': 5,
                'message': message,
                'overdue_kind': overdueKind,
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
    'either participant can confirm an overdue collection did not happen',
    (tester) async {
      for (final lender in [true, false]) {
        final submitted = <Map<String, dynamic>>[];
        await showTransaction(
          tester,
          status: 'RAGR',
          lender: lender,
          actions: ['confirm_no_collection'],
          overdueKind: 'collection',
          message: 'Past agreement date, transaction presumed not to occur.',
          submitted: submitted,
        );
        expect(find.text('Booking needs attention'), findsOneWidget);
        await tester.tap(find.text('Confirm collection did not happen'));
        await tester.pumpAndSettle();
        expect(submitted.single['action'], 'confirm_no_collection');
        await tester.pumpWidget(const SizedBox.shrink());
      }
    },
  );

  testWidgets(
    'overdue return prompts both parties but only lender can report non-return',
    (tester) async {
      for (final lender in [true, false]) {
        final submitted = <Map<String, dynamic>>[];
        await showTransaction(
          tester,
          status: 'RONG',
          lender: lender,
          actions: lender
              ? ['report_missing_return']
              : ['submit_return_borrower_evidence'],
          overdueKind: 'return',
          message: 'Has the renter returned the item?',
          submitted: submitted,
        );
        expect(find.text('Booking needs attention'), findsOneWidget);
        final button = find.text(
          'No, the item was not returned — start non-return review',
        );
        expect(button, lender ? findsOneWidget : findsNothing);
        if (lender) {
          await tester.tap(button);
          await tester.pumpAndSettle();
          expect(submitted.single['action'], 'report_missing_return');
        }
        await tester.pumpWidget(const SizedBox.shrink());
      }
    },
  );

  testWidgets('cancelled booking clearly replaces its stale current step', (
    tester,
  ) async {
    await showTransaction(
      tester,
      status: 'CACK',
      lender: true,
      actions: [],
      depositNotes: '[NO_COLLECTION_CONFIRMED] Collection did not happen.',
    );
    expect(find.text('Booking status'), findsOneWidget);
    expect(find.text('Cancelled'), findsWidgets);
    expect(
      find.text(
        'This booking was cancelled because collection did not happen.',
      ),
      findsWidgets,
    );
    expect(find.text('Current step'), findsNothing);
    expect(
      find.text(
        'No direct actions available right now. Use messages to coordinate the next step.',
      ),
      findsNothing,
    );
  });

  testWidgets(
    'lender can open checkout evidence; renter does not see handover panel',
    (tester) async {
      const channel = MethodChannel('plugins.flutter.io/url_launcher');
      final opened = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, (
        call,
      ) async {
        if (call.method == 'launch')
          opened.add(call.arguments['url'] as String);
        return true;
      });
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          channel,
          null,
        ),
      );
      for (final lender in [true, false]) {
        await showTransaction(
          tester,
          status: 'RDAYAWV',
          lender: lender,
          actions: [],
          evidence: [
            {
              'id': 1,
              'evidence_stage': 'checkout_lender',
              'video_url': 'https://example.test/evidence.mp4',
              'preview_url': 'https://example.test/preview.mp4',
              'download_url': 'https://example.test/download/',
              'preview_status': 'ready',
            },
          ],
        );
        final handoverPanel = find.text('Checkout Handover Evidence');
        if (lender) {
          expect(handoverPanel, findsOneWidget);
          final watch = find.text('Watch preview');
          expect(watch, findsOneWidget);
          await tester.ensureVisible(watch);
          await tester.tap(watch);
          await tester.pumpAndSettle();
          expect(opened.last, 'https://example.test/preview.mp4');
          final download = find.text('Download full uploaded quality');
          await tester.ensureVisible(download);
          await tester.tap(download);
          await tester.pumpAndSettle();
          expect(opened.last, 'https://example.test/preview.mp4');
        } else {
          expect(handoverPanel, findsNothing);
        }
        await dispose(tester);
      }
      expect(opened.length, 1);
    },
  );

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
    expect(find.text('Accept Condition & Show Collection Code'), findsOneWidget);
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
    final verify = find.text('Collection confirmed');
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
    expect(find.text('Accept Condition & Show Return Code'), findsOneWidget);
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
