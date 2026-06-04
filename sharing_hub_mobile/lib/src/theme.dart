import 'package:flutter/material.dart';

class SharingHubPalette {
  static const brandTeal = Color(0xFF2EC4B6);
  static const accentCoral = Color(0xFFF05C2A);

  static const lightBackground = Color(0xFFF7F4EE);
  static const lightBackgroundAlt = Color(0xFFEEF8F6);
  static const lightSurface = Color(0xFFFFFFFF);
  static const lightSurfaceSoft = Color(0xFFF7FCFB);
  static const lightBorder = Color(0xFFD7EBE7);
  static const lightText = Color(0xFF1F3F4B);
  static const lightTextMuted = Color(0xFF56707A);

  static const darkBackground = Color(0xFF0F1F26);
  static const darkBackgroundAlt = Color(0xFF1B343D);
  static const darkSurface = Color(0xFF1F3B44);
  static const darkSurfaceSoft = Color(0xFF294B55);
  static const darkBorder = Color(0xFF2F5661);
  static const darkText = Color(0xFFE8F3F1);
  static const darkTextMuted = Color(0xFFA5C0C7);
}

List<Color> sharingHubBackgroundGradient(Brightness brightness) {
  if (brightness == Brightness.dark) {
    return const [
      SharingHubPalette.darkBackground,
      SharingHubPalette.darkBackgroundAlt,
    ];
  }
  return const [
    SharingHubPalette.lightBackground,
    SharingHubPalette.lightBackgroundAlt,
  ];
}

final ThemeData sharingHubLightTheme = ThemeData(
  useMaterial3: true,
  brightness: Brightness.light,
  primaryColor: SharingHubPalette.brandTeal,
  colorScheme: ColorScheme.fromSwatch(brightness: Brightness.light).copyWith(
    primary: SharingHubPalette.brandTeal,
    secondary: SharingHubPalette.accentCoral,
    surface: SharingHubPalette.lightSurface,
  ),
  scaffoldBackgroundColor: SharingHubPalette.lightBackground,
  fontFamily: 'Nunito',
  appBarTheme: const AppBarTheme(
    backgroundColor: SharingHubPalette.lightBackground,
    elevation: 0,
    iconTheme: IconThemeData(color: SharingHubPalette.brandTeal),
    titleTextStyle: TextStyle(
      color: SharingHubPalette.lightText,
      fontWeight: FontWeight.bold,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: SharingHubPalette.lightBorder),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: SharingHubPalette.lightBorder),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(
        color: SharingHubPalette.brandTeal,
        width: 2,
      ),
    ),
    filled: true,
    fillColor: const Color(0xFFFCFFFE),
    contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
    hintStyle: const TextStyle(color: SharingHubPalette.lightTextMuted),
  ),
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      foregroundColor: SharingHubPalette.lightText,
      side: const BorderSide(color: SharingHubPalette.lightBorder, width: 1.5),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 20),
    ),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: SharingHubPalette.brandTeal,
      foregroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      textStyle: const TextStyle(
        fontWeight: FontWeight.bold,
        fontSize: 18,
        fontFamily: 'Nunito',
      ),
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 32),
    ),
  ),
  textTheme: const TextTheme(
    headlineLarge: TextStyle(
      color: SharingHubPalette.lightText,
      fontWeight: FontWeight.bold,
      fontSize: 34,
      fontFamily: 'Nunito',
    ),
    headlineMedium: TextStyle(
      color: SharingHubPalette.lightText,
      fontWeight: FontWeight.bold,
      fontSize: 28,
      fontFamily: 'Nunito',
    ),
    titleLarge: TextStyle(
      color: SharingHubPalette.lightText,
      fontWeight: FontWeight.w800,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
    titleMedium: TextStyle(
      color: SharingHubPalette.lightText,
      fontWeight: FontWeight.w700,
      fontSize: 17,
      fontFamily: 'Nunito',
    ),
    bodyLarge: TextStyle(
      color: SharingHubPalette.lightText,
      fontSize: 18,
      fontFamily: 'Nunito',
    ),
    bodyMedium: TextStyle(
      color: SharingHubPalette.lightText,
      fontSize: 15,
      height: 1.35,
      fontFamily: 'Nunito',
    ),
    bodySmall: TextStyle(
      color: SharingHubPalette.lightTextMuted,
      fontSize: 13,
      height: 1.25,
      fontFamily: 'Nunito',
    ),
    labelLarge: TextStyle(
      color: SharingHubPalette.lightText,
      fontWeight: FontWeight.bold,
      fontSize: 16,
      fontFamily: 'Nunito',
    ),
  ),
  cardTheme: CardThemeData(
    color: SharingHubPalette.lightSurfaceSoft,
    surfaceTintColor: Colors.transparent,
    elevation: 0,
    margin: const EdgeInsets.symmetric(vertical: 8),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: BorderSide(color: SharingHubPalette.brandTeal, width: 1.5),
    ),
  ),
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    minLeadingWidth: 56,
    horizontalTitleGap: 12,
  ),
  chipTheme: ChipThemeData(
    backgroundColor: SharingHubPalette.lightSurfaceSoft,
    selectedColor: const Color(0xFFDDF3EE),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    labelStyle: const TextStyle(
      color: SharingHubPalette.lightText,
      fontFamily: 'Nunito',
    ),
    side: const BorderSide(color: SharingHubPalette.lightBorder),
  ),
  bottomNavigationBarTheme: const BottomNavigationBarThemeData(
    backgroundColor: SharingHubPalette.lightSurface,
    selectedItemColor: SharingHubPalette.brandTeal,
    unselectedItemColor: SharingHubPalette.lightTextMuted,
    showUnselectedLabels: true,
    selectedLabelStyle: TextStyle(fontWeight: FontWeight.w700),
    type: BottomNavigationBarType.fixed,
  ),
);

final ThemeData sharingHubDarkTheme = ThemeData(
  useMaterial3: true,
  brightness: Brightness.dark,
  primaryColor: SharingHubPalette.brandTeal,
  colorScheme: ColorScheme.fromSwatch(brightness: Brightness.dark).copyWith(
    primary: SharingHubPalette.brandTeal,
    secondary: SharingHubPalette.accentCoral,
    surface: SharingHubPalette.darkSurface,
  ),
  scaffoldBackgroundColor: SharingHubPalette.darkBackground,
  fontFamily: 'Nunito',
  appBarTheme: const AppBarTheme(
    backgroundColor: SharingHubPalette.darkBackground,
    elevation: 0,
    iconTheme: IconThemeData(color: SharingHubPalette.brandTeal),
    titleTextStyle: TextStyle(
      color: SharingHubPalette.darkText,
      fontWeight: FontWeight.bold,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: SharingHubPalette.darkBorder),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: SharingHubPalette.darkBorder),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(
        color: SharingHubPalette.brandTeal,
        width: 2,
      ),
    ),
    filled: true,
    fillColor: SharingHubPalette.darkSurface,
    contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
    hintStyle: const TextStyle(color: SharingHubPalette.darkTextMuted),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: SharingHubPalette.brandTeal,
      foregroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      textStyle: const TextStyle(
        fontWeight: FontWeight.bold,
        fontSize: 18,
        fontFamily: 'Nunito',
      ),
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 32),
    ),
  ),
  textTheme: const TextTheme(
    headlineLarge: TextStyle(
      color: SharingHubPalette.darkText,
      fontWeight: FontWeight.bold,
      fontSize: 34,
      fontFamily: 'Nunito',
    ),
    headlineMedium: TextStyle(
      color: SharingHubPalette.darkText,
      fontWeight: FontWeight.bold,
      fontSize: 28,
      fontFamily: 'Nunito',
    ),
    titleLarge: TextStyle(
      color: SharingHubPalette.darkText,
      fontWeight: FontWeight.w800,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
    titleMedium: TextStyle(
      color: SharingHubPalette.darkText,
      fontWeight: FontWeight.w700,
      fontSize: 17,
      fontFamily: 'Nunito',
    ),
    bodyLarge: TextStyle(
      color: SharingHubPalette.darkText,
      fontSize: 18,
      fontFamily: 'Nunito',
    ),
    bodyMedium: TextStyle(
      color: SharingHubPalette.darkText,
      fontSize: 15,
      height: 1.35,
      fontFamily: 'Nunito',
    ),
    bodySmall: TextStyle(
      color: SharingHubPalette.darkTextMuted,
      fontSize: 13,
      height: 1.25,
      fontFamily: 'Nunito',
    ),
    labelLarge: TextStyle(
      color: SharingHubPalette.darkText,
      fontWeight: FontWeight.bold,
      fontSize: 16,
      fontFamily: 'Nunito',
    ),
  ),
  cardTheme: CardThemeData(
    color: SharingHubPalette.darkSurfaceSoft,
    surfaceTintColor: Colors.transparent,
    elevation: 0,
    margin: const EdgeInsets.symmetric(vertical: 8),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: BorderSide(color: SharingHubPalette.brandTeal, width: 1.5),
    ),
  ),
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    minLeadingWidth: 56,
    horizontalTitleGap: 12,
  ),
  chipTheme: ChipThemeData(
    backgroundColor: SharingHubPalette.darkSurface,
    selectedColor: SharingHubPalette.darkSurfaceSoft,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    labelStyle: const TextStyle(
      color: SharingHubPalette.darkText,
      fontFamily: 'Nunito',
    ),
    side: const BorderSide(color: SharingHubPalette.darkBorder),
  ),
  bottomNavigationBarTheme: const BottomNavigationBarThemeData(
    backgroundColor: SharingHubPalette.darkSurface,
    selectedItemColor: SharingHubPalette.brandTeal,
    unselectedItemColor: SharingHubPalette.darkTextMuted,
    showUnselectedLabels: true,
    selectedLabelStyle: TextStyle(fontWeight: FontWeight.w700),
    type: BottomNavigationBarType.fixed,
  ),
);

// For backwards compatibility
@Deprecated('Use sharingHubLightTheme instead')
final ThemeData sharingHubTheme = sharingHubLightTheme;
