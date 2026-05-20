class AppConfig {
  // Override at launch: --dart-define=API_BASE_URL=http://<your-lan-ip>:8000/api/v1
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://192.168.1.155:8000/api/v1',
  );
}
