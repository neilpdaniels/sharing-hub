import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class RentalutionPalette {
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

List<Color> rentalutionBackgroundGradient(Brightness brightness) {
  if (brightness == Brightness.dark) {
    return const [
      RentalutionPalette.darkBackground,
      RentalutionPalette.darkBackgroundAlt,
    ];
  }
  return const [
    RentalutionPalette.lightBackground,
    RentalutionPalette.lightBackgroundAlt,
  ];
}

final ThemeData rentalutionLightTheme = ThemeData(
  useMaterial3: true,
  brightness: Brightness.light,
  primaryColor: RentalutionPalette.brandTeal,
  colorScheme: ColorScheme.fromSwatch(brightness: Brightness.light).copyWith(
    primary: RentalutionPalette.brandTeal,
    secondary: RentalutionPalette.accentCoral,
    surface: RentalutionPalette.lightSurface,
  ),
  scaffoldBackgroundColor: RentalutionPalette.lightBackground,
  textTheme: GoogleFonts.manropeTextTheme().copyWith(
    headlineLarge: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w800,
      fontSize: 30,
    ),
    headlineMedium: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w800,
      fontSize: 24,
    ),
    headlineSmall: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w800,
      fontSize: 20,
    ),
    titleLarge: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w800,
      fontSize: 20,
    ),
    titleMedium: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w700,
      fontSize: 17,
    ),
    titleSmall: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w700,
      fontSize: 15,
    ),
    bodyLarge: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontSize: 16,
    ),
    bodyMedium: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontSize: 15,
      height: 1.35,
    ),
    bodySmall: GoogleFonts.manrope(
      color: RentalutionPalette.lightTextMuted,
      fontSize: 13,
      height: 1.25,
    ),
    labelLarge: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w700,
      fontSize: 15,
    ),
    labelMedium: GoogleFonts.manrope(
      color: RentalutionPalette.lightTextMuted,
      fontWeight: FontWeight.w600,
      fontSize: 13,
    ),
    labelSmall: GoogleFonts.manrope(
      color: RentalutionPalette.lightTextMuted,
      fontWeight: FontWeight.w600,
      fontSize: 12,
    ),
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: RentalutionPalette.lightBackground,
    elevation: 0,
    iconTheme: IconThemeData(color: RentalutionPalette.brandTeal),
    titleTextStyle: TextStyle(
      color: RentalutionPalette.lightText,
      fontWeight: FontWeight.w800,
      fontSize: 20,
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: RentalutionPalette.lightBorder),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: RentalutionPalette.lightBorder),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(
        color: RentalutionPalette.brandTeal,
        width: 2,
      ),
    ),
    filled: true,
    fillColor: const Color(0xFFFCFFFE),
    contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
    hintStyle: const TextStyle(color: RentalutionPalette.lightTextMuted),
  ),
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      foregroundColor: RentalutionPalette.lightText,
      side: const BorderSide(color: RentalutionPalette.lightBorder, width: 1.5),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 20),
    ),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: RentalutionPalette.brandTeal,
      foregroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      textStyle: GoogleFonts.manrope(
        fontWeight: FontWeight.bold,
        fontSize: 15,
      ),
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 32),
    ),
  ),
  cardTheme: CardThemeData(
    color: RentalutionPalette.lightSurfaceSoft,
    surfaceTintColor: Colors.transparent,
    elevation: 0,
    margin: const EdgeInsets.symmetric(vertical: 8),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: BorderSide(color: RentalutionPalette.brandTeal, width: 1.5),
    ),
  ),
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    minLeadingWidth: 56,
    horizontalTitleGap: 12,
  ),
  chipTheme: ChipThemeData(
    backgroundColor: RentalutionPalette.lightSurfaceSoft,
    selectedColor: const Color(0xFFDDF3EE),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    labelStyle: GoogleFonts.manrope(
      color: RentalutionPalette.lightText,
      fontSize: 13,
      fontWeight: FontWeight.w600,
    ),
    side: const BorderSide(color: RentalutionPalette.lightBorder),
  ),
  bottomNavigationBarTheme: const BottomNavigationBarThemeData(
    backgroundColor: RentalutionPalette.lightSurface,
    selectedItemColor: RentalutionPalette.brandTeal,
    unselectedItemColor: RentalutionPalette.lightTextMuted,
    showUnselectedLabels: true,
    selectedLabelStyle: TextStyle(fontWeight: FontWeight.w700),
    type: BottomNavigationBarType.fixed,
  ),
);

final ThemeData rentalutionDarkTheme = ThemeData(
  useMaterial3: true,
  brightness: Brightness.dark,
  primaryColor: RentalutionPalette.brandTeal,
  colorScheme: ColorScheme.fromSwatch(brightness: Brightness.dark).copyWith(
    primary: RentalutionPalette.brandTeal,
    secondary: RentalutionPalette.accentCoral,
    surface: RentalutionPalette.darkSurface,
  ),
  scaffoldBackgroundColor: RentalutionPalette.darkBackground,
  textTheme: GoogleFonts.manropeTextTheme(ThemeData.dark().textTheme).copyWith(
    headlineLarge: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w800,
      fontSize: 30,
    ),
    headlineMedium: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w800,
      fontSize: 24,
    ),
    headlineSmall: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w800,
      fontSize: 20,
    ),
    titleLarge: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w800,
      fontSize: 20,
    ),
    titleMedium: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w700,
      fontSize: 17,
    ),
    titleSmall: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w700,
      fontSize: 15,
    ),
    bodyLarge: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontSize: 16,
    ),
    bodyMedium: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontSize: 15,
      height: 1.35,
    ),
    bodySmall: GoogleFonts.manrope(
      color: RentalutionPalette.darkTextMuted,
      fontSize: 13,
      height: 1.25,
    ),
    labelLarge: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w700,
      fontSize: 15,
    ),
    labelMedium: GoogleFonts.manrope(
      color: RentalutionPalette.darkTextMuted,
      fontWeight: FontWeight.w600,
      fontSize: 13,
    ),
    labelSmall: GoogleFonts.manrope(
      color: RentalutionPalette.darkTextMuted,
      fontWeight: FontWeight.w600,
      fontSize: 12,
    ),
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: RentalutionPalette.darkBackground,
    elevation: 0,
    iconTheme: IconThemeData(color: RentalutionPalette.brandTeal),
    titleTextStyle: TextStyle(
      color: RentalutionPalette.darkText,
      fontWeight: FontWeight.w800,
      fontSize: 20,
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: RentalutionPalette.darkBorder),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: RentalutionPalette.darkBorder),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(
        color: RentalutionPalette.brandTeal,
        width: 2,
      ),
    ),
    filled: true,
    fillColor: RentalutionPalette.darkSurface,
    contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
    hintStyle: const TextStyle(color: RentalutionPalette.darkTextMuted),
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: RentalutionPalette.brandTeal,
      foregroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      textStyle: GoogleFonts.manrope(
        fontWeight: FontWeight.bold,
        fontSize: 15,
      ),
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 32),
    ),
  ),
  cardTheme: CardThemeData(
    color: RentalutionPalette.darkSurfaceSoft,
    surfaceTintColor: Colors.transparent,
    elevation: 0,
    margin: const EdgeInsets.symmetric(vertical: 8),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: BorderSide(color: RentalutionPalette.brandTeal, width: 1.5),
    ),
  ),
  listTileTheme: const ListTileThemeData(
    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    minLeadingWidth: 56,
    horizontalTitleGap: 12,
  ),
  chipTheme: ChipThemeData(
    backgroundColor: RentalutionPalette.darkSurface,
    selectedColor: RentalutionPalette.darkSurfaceSoft,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    labelStyle: GoogleFonts.manrope(
      color: RentalutionPalette.darkText,
      fontSize: 13,
      fontWeight: FontWeight.w600,
    ),
    side: const BorderSide(color: RentalutionPalette.darkBorder),
  ),
  bottomNavigationBarTheme: const BottomNavigationBarThemeData(
    backgroundColor: RentalutionPalette.darkSurface,
    selectedItemColor: RentalutionPalette.brandTeal,
    unselectedItemColor: RentalutionPalette.darkTextMuted,
    showUnselectedLabels: true,
    selectedLabelStyle: TextStyle(fontWeight: FontWeight.w700),
    type: BottomNavigationBarType.fixed,
  ),
);
