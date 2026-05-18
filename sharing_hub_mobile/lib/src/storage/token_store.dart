import 'package:shared_preferences/shared_preferences.dart';

class TokenStore {
  static const _accessKey = 'auth_access_token';
  static const _refreshKey = 'auth_refresh_token';
  static const _biometricEnabledKey = 'biometric_unlock_enabled';

  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, accessToken);
    await prefs.setString(_refreshKey, refreshToken);
  }

  Future<String?> getAccessToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_accessKey);
  }

  Future<String?> getRefreshToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_refreshKey);
  }

  Future<bool> hasSavedSession() async {
    final prefs = await SharedPreferences.getInstance();
    final access = prefs.getString(_accessKey);
    final refresh = prefs.getString(_refreshKey);
    return access != null && access.isNotEmpty && refresh != null && refresh.isNotEmpty;
  }

  Future<bool> isBiometricUnlockEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_biometricEnabledKey) ?? false;
  }

  Future<void> setBiometricUnlockEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_biometricEnabledKey, enabled);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }
}
