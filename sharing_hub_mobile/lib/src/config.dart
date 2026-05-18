class AppConfig {
  // Android emulator should use 10.0.2.2 for localhost.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );
}
