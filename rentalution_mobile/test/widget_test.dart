import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:rentalution_mobile/src/screens/login_screen.dart';

void main() {
  testWidgets('login screen renders', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(
          busy: false,
          onLogin: (login, password) async {},
        ),
      ),
    );

    expect(find.text('Email or username'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Create account'), findsOneWidget);
  });
}
