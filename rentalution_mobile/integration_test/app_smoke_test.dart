import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:rentalution_mobile/src/screens/login_screen.dart';

/// Runs on a real Android/iOS device or emulator, not just Flutter's widget VM.
///
/// The payout journey itself requires an authenticated test API fixture. Keep
/// that fixture separate from this smoke test so no real account, Stripe URL,
/// or test credentials are embedded in the mobile app repository.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('login entry point renders on a target device', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: LoginScreen(busy: false, onLogin: (_, _) async {})),
    );

    expect(find.text('Email or username'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
  });
}
