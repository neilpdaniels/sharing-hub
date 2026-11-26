import 'package:shared_preferences/shared_preferences.dart';

class ThemeService {
  static const String _themeKey = 'isDarkMode';

  Future<bool?> isDarkMode() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_themeKey);
  }

  Future<void> setDarkMode(bool? isDark) async {
    final prefs = await SharedPreferences.getInstance();
    if (isDark == null) {
      await prefs.remove(_themeKey);
    } else {
      await prefs.setBool(_themeKey, isDark);
    }
  }

}
