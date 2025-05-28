//lib/player/media_kit_initializer.dart 
/*
* Use only once!!
* example /lib/utils/app_startup.dart
*/
import 'package:media_kit/media_kit.dart';

void initializeMediaKitIfNeeded() {
  // Stellen Sie sicher, dass dies nur einmal aufgerufen wird.
  // MediaKit.ensureInitialized() ist idempotent, kann also mehrfach aufgerufen werden,
  // aber es ist am besten, es nur einmal am Startpunkt aufzurufen.
  MediaKit.ensureInitialized();
}

