import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';

/// A device-local override for development builds when a laptop's LAN IP changes.
class DevApiEndpointStore {
  static const _key = 'dev_api_base_url';
  static const _port = 8000;
  static const _apiPath = '/api/v1';

  bool get isAvailable => AppConfig.appName.toLowerCase().contains('dev');

  Future<String> getBaseUrl() async {
    if (!isAvailable) return AppConfig.baseUrl;
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_key) ?? AppConfig.baseUrl;
  }

  /// Saves a hostname or IPv4 address. The local Django port and API path are
  /// deliberately fixed so changing networks only needs the new address.
  Future<void> save(String host) async {
    final normalisedHost = host.trim().toLowerCase();
    final invalidHost =
        normalisedHost.isEmpty ||
        normalisedHost.contains(RegExp(r'[:/@?#\s]')) ||
        normalisedHost.contains('://') ||
        !RegExp(
          r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$|^[a-z0-9]$',
        ).hasMatch(normalisedHost);
    if (!isAvailable || invalidHost) {
      throw const FormatException(
        'Enter only the laptop IP address or hostname.',
      );
    }

    final normalised = 'http://$normalisedHost:$_port$_apiPath';
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, normalised);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
