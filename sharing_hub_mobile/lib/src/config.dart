class AppConfig {
  // Override at launch: --dart-define=API_BASE_URL=http://<your-lan-ip>:8000/api/v1
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://192.168.1.155:8000/api/v1',
  );

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

  static String get websiteBaseUrl {
    if (baseUrl.contains('/api/')) {
      return baseUrl.split('/api/').first;
    }
    if (baseUrl.endsWith('/api')) {
      return baseUrl.substring(0, baseUrl.length - 4);
    }
    return baseUrl;
  }
}
