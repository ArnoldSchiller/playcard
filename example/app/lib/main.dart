// lib/main.dart

import 'package:flutter/material.dart';
import 'package:playcard_app/screens/radio_status_screen.dart';
import 'package:playcard_app/config/app_theme.dart';
import 'package:playcard_app/config/constants.dart';
import 'package:playcard_app/utils/app_startup.dart';

// KEIN Import für flutter_gen/gen_l10n/app_localizations.dart mehr hier!

void main() {
  runApp(const MyAppRoot());
}


class MyAppRoot extends StatelessWidget {
  const MyAppRoot({super.key});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder(
      future: AppStartup.initializeApp(), // Rufe die Initialisierungsfunktion auf
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.done) {
          // Wenn die Initialisierung abgeschlossen ist, zeige die eigentliche App
          return AppStartup.setupProviders( // Provider einrichten
            child: const PlaycardApp(),
          );
        } else {
          // Während der Initialisierung, zeige einen Ladebildschirm
          return MaterialApp(
            title: kAppName,
            theme: darkTheme, // oder lightTheme, je nach Präferenz für den Splash Screen
            // KEINE Lokalisierungseinstellungen mehr hier!
            home: const Scaffold(
              body: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 20),
                    // Text hardcodiert auf Englisch (oder andere gewünschte Sprache)
                    Text('Loading app...', style: TextStyle(fontSize: 18)),
                  ],
                ),
              ),
            ),
          );
        }
      },
    );
  }
}

class PlaycardApp extends StatelessWidget {
  const PlaycardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: kAppName,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: ThemeMode.system,
      // KEINE Lokalisierungseinstellungen mehr hier!
      home: const RadioStatusScreen(),
    );
  }
}
