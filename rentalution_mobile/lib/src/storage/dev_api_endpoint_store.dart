import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';

/// A device-local override for development builds when a laptop's LAN IP changes.
class DevApiEndpointStore {
  static const _key = 'dev_api_base_url';

  bool get isAvailable => AppConfig.appName.toLowerCase().contains('dev');

  Future<String> getBaseUrl() async {
    if (!isAvailable) return AppConfig.baseUrl;
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_key) ?? AppConfig.baseUrl;
  }

  Future<void> save(String baseUrl) async {
    final uri = Uri.tryParse(baseUrl.trim());
    if (!isAvailable ||
        uri == null ||
        !uri.hasAuthority ||
        (uri.scheme != 'http' && uri.scheme != 'https')) {
      throw const FormatException(
        'Enter a full http:// or https:// server address.',
      );
    }
    final normalised = uri
        .replace(path: '/api/v1', query: null, fragment: null)
        .toString()
        .replaceAll(RegExp(r'/$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, normalised);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
