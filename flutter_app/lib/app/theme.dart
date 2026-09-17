import 'package:flutter/material.dart';

class AppTheme {
  // Colors
  static const Color primary = Color(0xFF2E7D32);
  static const Color primaryDark = Color(0xFF1B5E20);
  static const Color primaryLight = Color(0xFFE8F5E9);

  static const Color background = Color(0xFFF7F9F7);
  static const Color surface = Color(0xFFFFFFFF);

  static const Color text = Color(0xFF172018);
  static const Color secondaryText = Color(0xFF5F6B61);
  static const Color border = Color(0xFFDDE3DE);

  static const Color success = Color(0xFF2E7D32);
  static const Color warning = Color(0xFFF9A825);
  static const Color moderate = Color(0xFFEF8F00);
  static const Color error = Color(0xFFC62828);
  static const Color emergency = Color(0xFFD32F2F);
  static const Color info = Color(0xFF1565C0);
  static const Color offline = Color(0xFF757575);

  static ThemeData get lightTheme {
    return ThemeData(
      primaryColor: primary,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme.light(
        primary: primary,
        secondary: primaryDark,
        surface: surface,
        error: error,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: text,
        onError: Colors.white,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: primary,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
      ),
      fontFamily: 'Inter',
      textTheme: const TextTheme(
        displayLarge: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: text),
        headlineLarge: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: text),
        headlineMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: text),
        headlineSmall: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: text),
        bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, color: text),
        bodyMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.w400, color: text),
        labelLarge: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: text),
        labelSmall: TextStyle(fontSize: 12, fontWeight: FontWeight.w400, color: secondaryText),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 2,
        shadowColor: Colors.black.withValues(alpha: 0.1),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: border, width: 1),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: surface,
        selectedItemColor: primary,
        unselectedItemColor: secondaryText,
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
    );
  }
}
