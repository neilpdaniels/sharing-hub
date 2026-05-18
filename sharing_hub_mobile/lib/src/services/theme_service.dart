import 'package:shared_preferences/shared_preferences.dart';

class ThemeService {
  static const String _themeKey = 'isDarkMode';

  Future<bool> isDarkMode() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_themeKey) ?? false;
  }

  Future<void> setDarkMode(bool isDark) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_themeKey, isDark);
  }

  Future<void> toggleDarkMode() async {
    final prefs = await SharedPreferences.getInstance();
    final isDark = prefs.getBool(_themeKey) ?? false;
    await prefs.setBool(_themeKey, !isDark);
  }
}
