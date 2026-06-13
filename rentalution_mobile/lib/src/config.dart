class AppConfig {
  // Override at launch: --dart-define=API_BASE_URL=http://<your-lan-ip>:8000/api/v1
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://192.168.1.155:8000/api/v1',
  );

  static String get websiteBaseUrl {
    final uri = Uri.parse(baseUrl);
    final segments = uri.pathSegments;
    final isApiV1 = segments.length >= 2 &&
        segments[0] == 'api' &&
        segments[1] == 'v1';
    if (isApiV1) {
      return uri.replace(pathSegments: []).toString().replaceAll(RegExp(r'/$'), '');
    }
    return uri.replace(pathSegments: []).toString().replaceAll(RegExp(r'/$'), '');
  }

  // Override at launch: --dart-define=STRIPE_PUBLISHABLE_KEY=pk_test_...
  static const String stripePublishableKey = String.fromEnvironment(
    'STRIPE_PUBLISHABLE_KEY',
    defaultValue: '',
  );

  // Override at launch: --dart-define=TRANSACTION_LIVE_POLL_SECONDS=3
  static const int transactionLivePollSeconds = int.fromEnvironment(
    'TRANSACTION_LIVE_POLL_SECONDS',
    defaultValue: 3,
  );
}
