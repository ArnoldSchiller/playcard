// lib/utils/app_startup.dart

import 'package:flutter/material.dart';
import 'package:playcard_app/player/media_kit_initializer.dart';
import 'package:provider/provider.dart';
import 'package:playcard_app/providers/search_provider.dart';
import 'package:playcard_app/config/constants.dart';
import 'package:playcard_app/providers/media_player_provider.dart'; // <--- DIESER IMPORT IST NEU HIER


class AppStartup {
  static Future<void> initializeApp() async {
    // Sicherstellen, dass WidgetsBinding initialisiert ist
    WidgetsFlutterBinding.ensureInitialized();

    // 1. MediaKit initialisieren
    ////print('AppStartup: Initialisiere MediaKit...');
    initializeMediaKitIfNeeded();
    ////print('AppStartup: MediaKit Initialisierung abgeschlossen.');

    // 2. Andere wichtige Initialisierungen (asynchron)
    // Hier könnten zukünftig weitere Dienste oder Bibliotheken initialisiert werden.
    // Beispiel:
    // await Firebase.initializeApp();
    // await SentryFlutter.init(...);
    // await SharedPreferences.getInstance(); // Für lokale Daten

    // Simuliere eine kurze Ladezeit, damit der Splash Screen sichtbar ist
    await Future.delayed(const Duration(milliseconds: 1500));

    ////print('AppStartup: Alle Initialisierungen abgeschlossen.');
  }

  // Dies ist eine Hilfsfunktion, um die Provider zentral zu definieren
  // und in `main.dart` zu verwenden.
  static Widget setupProviders({required Widget child}) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => SearchProvider()),
        ChangeNotifierProvider(create: (_) => MediaPlayerProvider()), // <--- HIER DEN NEUEN PROVIDER HINZUFÜGEN
        // Zukünftige Provider können hier einfach hinzugefügt werden
      ],
      child: child,
    );
  }
}
