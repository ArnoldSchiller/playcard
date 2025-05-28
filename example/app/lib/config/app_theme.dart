// lib/config/app_theme.dart
import 'package:flutter/material.dart';
import 'package:playcard_app/config/constants.dart';

// Definition des dunklen Themas, basierend auf Ihrem ursprünglichen Design
final ThemeData darkTheme = ThemeData(
  useMaterial3: true,
  colorScheme: const ColorScheme(
    brightness: Brightness.dark,
    primary: Color(0xFF1A237E), // Dunkelblau
    onPrimary: Colors.white,
    primaryContainer: Color(0xFFFA237E), // Ihr Gold-Akzent
    onPrimaryContainer: Colors.white,
    secondary: Color(0xFFD4AF37), // Ihr Gold-Akzent
    onSecondary: Colors.black,
    secondaryContainer: Color(0xFFFDD835), // Ihr Gold-Akzent
    onSecondaryContainer: Colors.black,
    tertiary: Color(0xFFD4AF37), // Ihr Gold-Akzent
    onTertiary: Colors.black,
    tertiaryContainer: Color(0xFFBBDEFB),
    onTertiaryContainer: Colors.black,
    error: Color(0xFFCF6679),
    onError: Colors.black,
    errorContainer: Color(0xFFB00020),
    onErrorContainer: Colors.white,
    background: Color(0xFF0D123F), // Dunkler Hintergrund
    onBackground: Colors.white,
    surface: Color(0xFF12184B), // Dunklere Oberfläche für Karten etc.
    onSurface: Colors.white,
    surfaceVariant: Color(0xFF242A5C),
    onSurfaceVariant: Colors.white,
    outline: Color(0xFF444466),
    shadow: Colors.black,
    inverseSurface: Colors.white,
    onInverseSurface: Colors.black,
    inversePrimary: Color(0xFF9FA8DA),
    scrim: Colors.black54,
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFF444466), // Dunkles Lila/Grau für AppBar
    foregroundColor: Colors.white,
    titleTextStyle: TextStyle(
      color: Colors.white,
      fontSize: 20,
      fontWeight: FontWeight.bold,
    ),
  ),
  cardTheme: const CardThemeData(
    color: Color(0xFF444466), // Dunkles Lila/Grau für Karten
    elevation: 4,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.all(Radius.circular(8)),
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: Color(0xFF283593), // Dunkelblau für Input-Felder
    hintStyle: TextStyle(color: Colors.white70),
    labelStyle: TextStyle(color: Colors.white),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8.0),
      borderSide: BorderSide.none,
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8.0),
      borderSide: BorderSide(color: Color(0xFFD4AF37), width: 2), // Goldene Fokuslinie
    ),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8.0),
      borderSide: BorderSide.none,
    ),
  ),
  textTheme: const TextTheme(
    bodyLarge: TextStyle(color: Colors.white),
    bodyMedium: TextStyle(color: Colors.white70),
    headlineSmall: TextStyle(color: Color(0xFFD4AF37)), // Gold für Überschriften
    titleMedium: TextStyle(color: Colors.white),
    titleSmall: TextStyle(color: Colors.white70),
  ),
);

// Definition des hellen Themas (Beispiel - kann angepasst werden)
final ThemeData lightTheme = ThemeData(
  useMaterial3: true,
  colorScheme: const ColorScheme(
    brightness: Brightness.light,
    primary: Color(0xFF673AB7), // Deep Purple
    onPrimary: Colors.white,
    primaryContainer: Color(0xFFEDE7F6),
    onPrimaryContainer: Colors.black,
    secondary: Color(0xFFFFC107), // Amber
    onSecondary: Colors.black,
    secondaryContainer: Color(0xFFFFECB3),
    onSecondaryContainer: Colors.black,
    tertiary: Color(0xFF00BCD4), // Cyan
    onTertiary: Colors.black,
    tertiaryContainer: Color(0xFFE0F7FA),
    onTertiaryContainer: Colors.black,
    error: Color(0xFFB00020),
    onError: Colors.white,
    errorContainer: Color(0xFFFFCDD2),
    onErrorContainer: Colors.black,
    background: Colors.white,
    onBackground: Colors.black,
    surface: Color(0xFFF5F5F5), // Helle Oberfläche
    onSurface: Colors.black,
    surfaceVariant: Color(0xFFEEEEEE),
    onSurfaceVariant: Colors.black,
    outline: Color(0xFFBDBDBD),
    shadow: Colors.black54,
    inverseSurface: Colors.black87,
    onInverseSurface: Colors.white,
    inversePrimary: Color(0xFF9575CD),
    scrim: Colors.black54,
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFF673AB7), // Deep Purple
    foregroundColor: Colors.white,
    titleTextStyle: TextStyle(
      color: Colors.white,
      fontSize: 20,
      fontWeight: FontWeight.bold,
    ),
  ),
  cardTheme: const CardThemeData(
    color: Colors.white,
    elevation: 4,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.all(Radius.circular(8)),
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: Color(0xFFE0E0E0),
    hintStyle: TextStyle(color: Colors.black54),
    labelStyle: TextStyle(color: Colors.black),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8.0),
      borderSide: BorderSide.none,
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8.0),
      borderSide: BorderSide(color: Color(0xFFFFC107), width: 2),
    ),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8.0),
      borderSide: BorderSide.none,
    ),
  ),
  textTheme: const TextTheme(
    bodyLarge: TextStyle(color: Colors.black),
    bodyMedium: TextStyle(color: Colors.black87),
    headlineSmall: TextStyle(color: Color(0xFFFFC107)),
    titleMedium: TextStyle(color: Colors.black),
    titleSmall: TextStyle(color: Colors.black87),
  ),
);

// Optional: Ein Standard-Theme, wenn nicht explizit light oder dark gewählt
// Dies könnte einfach eines der beiden obigen sein oder eine Mischung
final ThemeData defaultTheme = darkTheme; // Beispiel: Standard ist das dunkle Thema
