import 'package:flutter/material.dart';

final ThemeData sharingHubLightTheme = ThemeData(
  useMaterial3: true,
  brightness: Brightness.light,
  primaryColor: const Color(0xFF0E9F9A),
  colorScheme: ColorScheme.fromSwatch(
    brightness: Brightness.light,
  ).copyWith(
    primary: const Color(0xFF0E9F9A),
    secondary: const Color(0xFFE07A2F),
    surface: const Color(0xFFF8F4EE),
  ),
  scaffoldBackgroundColor: const Color(0xFFF8F4EE),
  fontFamily: 'Nunito',
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFFF8F4EE),
    elevation: 0,
    iconTheme: IconThemeData(color: Color(0xFF0E9F9A)),
    titleTextStyle: TextStyle(
      color: Color(0xFF222B3A),
      fontWeight: FontWeight.bold,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFB7D3CF)),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFB7D3CF)),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFE07A2F), width: 2),
    ),
    filled: true,
    fillColor: const Color(0xFFFFFCF7),
    contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
    hintStyle: const TextStyle(color: Color(0xFF222B3A)),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: const Color(0xFF0E9F9A),
      foregroundColor: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
      ),
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
      color: Color(0xFF222B3A),
      fontWeight: FontWeight.bold,
      fontSize: 34,
      fontFamily: 'Nunito',
    ),
    headlineMedium: TextStyle(
      color: Color(0xFF222B3A),
      fontWeight: FontWeight.bold,
      fontSize: 28,
      fontFamily: 'Nunito',
    ),
    titleLarge: TextStyle(
      color: Color(0xFF222B3A),
      fontWeight: FontWeight.w800,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
    titleMedium: TextStyle(
      color: Color(0xFF22313F),
      fontWeight: FontWeight.w700,
      fontSize: 17,
      fontFamily: 'Nunito',
    ),
    bodyLarge: TextStyle(
      color: Color(0xFF222B3A),
      fontSize: 18,
      fontFamily: 'Nunito',
    ),
    bodyMedium: TextStyle(
      color: Color(0xFF222B3A),
      fontSize: 15,
      height: 1.35,
      fontFamily: 'Nunito',
    ),
    bodySmall: TextStyle(
      color: Color(0xFF51606F),
      fontSize: 13,
      height: 1.25,
      fontFamily: 'Nunito',
    ),
    labelLarge: TextStyle(
      color: Color(0xFFE07A2F),
      fontWeight: FontWeight.bold,
      fontSize: 16,
      fontFamily: 'Nunito',
    ),
  ),
  cardTheme: CardThemeData(
    color: const Color(0xFFFFFCF7),
    elevation: 0,
    margin: const EdgeInsets.symmetric(vertical: 8),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: Color(0xFFE4DDD4)),
    ),
  ),
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    minLeadingWidth: 56,
    horizontalTitleGap: 12,
  ),
  chipTheme: ChipThemeData(
    backgroundColor: const Color(0xFFE7F3F1),
    selectedColor: const Color(0xFFCFE8E4),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    labelStyle: const TextStyle(color: Color(0xFF222B3A), fontFamily: 'Nunito'),
    side: const BorderSide(color: Color(0xFFB7D3CF)),
  ),
  bottomNavigationBarTheme: const BottomNavigationBarThemeData(
    backgroundColor: Color(0xFFFFFCF7),
    selectedItemColor: Color(0xFF0E9F9A),
    unselectedItemColor: Color(0xFF6D6D6D),
    showUnselectedLabels: true,
    selectedLabelStyle: TextStyle(fontWeight: FontWeight.w700),
    type: BottomNavigationBarType.fixed,
  ),
);

final ThemeData sharingHubDarkTheme = ThemeData(
  useMaterial3: true,
  brightness: Brightness.dark,
  primaryColor: const Color(0xFF0E9F9A),
  colorScheme: ColorScheme.fromSwatch(
    brightness: Brightness.dark,
  ).copyWith(
    primary: const Color(0xFF0E9F9A),
    secondary: const Color(0xFFE07A2F),
    surface: const Color(0xFF1A2332),
  ),
  scaffoldBackgroundColor: const Color(0xFF0F1419),
  fontFamily: 'Nunito',
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFF1A2332),
    elevation: 0,
    iconTheme: IconThemeData(color: Color(0xFF0E9F9A)),
    titleTextStyle: TextStyle(
      color: Color(0xFFF8F4EE),
      fontWeight: FontWeight.bold,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFF2E4A5C)),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFF2E4A5C)),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFE07A2F), width: 2),
    ),
    filled: true,
    fillColor: const Color(0xFF1A2332),
    contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
    hintStyle: const TextStyle(color: Color(0xFF9CADB8)),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: const Color(0xFF0E9F9A),
      foregroundColor: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
      ),
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
      color: Color(0xFFF8F4EE),
      fontWeight: FontWeight.bold,
      fontSize: 34,
      fontFamily: 'Nunito',
    ),
    headlineMedium: TextStyle(
      color: Color(0xFFF8F4EE),
      fontWeight: FontWeight.bold,
      fontSize: 28,
      fontFamily: 'Nunito',
    ),
    titleLarge: TextStyle(
      color: Color(0xFFF8F4EE),
      fontWeight: FontWeight.w800,
      fontSize: 22,
      fontFamily: 'Nunito',
    ),
    titleMedium: TextStyle(
      color: Color(0xFFE0E8EF),
      fontWeight: FontWeight.w700,
      fontSize: 17,
      fontFamily: 'Nunito',
    ),
    bodyLarge: TextStyle(
      color: Color(0xFFE0E8EF),
      fontSize: 18,
      fontFamily: 'Nunito',
    ),
    bodyMedium: TextStyle(
      color: Color(0xFFC5D3DB),
      fontSize: 15,
      height: 1.35,
      fontFamily: 'Nunito',
    ),
    bodySmall: TextStyle(
      color: Color(0xFF9CADB8),
      fontSize: 13,
      height: 1.25,
      fontFamily: 'Nunito',
    ),
    labelLarge: TextStyle(
      color: Color(0xFFE07A2F),
      fontWeight: FontWeight.bold,
      fontSize: 16,
      fontFamily: 'Nunito',
    ),
  ),
  cardTheme: CardThemeData(
    color: const Color(0xFF1A2332),
    elevation: 0,
    margin: const EdgeInsets.symmetric(vertical: 8),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: Color(0xFF2E4A5C)),
    ),
  ),
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    minLeadingWidth: 56,
    horizontalTitleGap: 12,
  ),
  chipTheme: ChipThemeData(
    backgroundColor: const Color(0xFF2E4A5C),
    selectedColor: const Color(0xFF3D5E75),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    labelStyle: const TextStyle(color: Color(0xFFE0E8EF), fontFamily: 'Nunito'),
    side: const BorderSide(color: Color(0xFF3D5E75)),
  ),
  bottomNavigationBarTheme: const BottomNavigationBarThemeData(
    backgroundColor: Color(0xFF1A2332),
    selectedItemColor: Color(0xFF0E9F9A),
    unselectedItemColor: Color(0xFF6D7D8A),
    showUnselectedLabels: true,
    selectedLabelStyle: TextStyle(fontWeight: FontWeight.w700),
    type: BottomNavigationBarType.fixed,
  ),
);

// For backwards compatibility
@Deprecated('Use sharingHubLightTheme instead')
final ThemeData sharingHubTheme = sharingHubLightTheme;
