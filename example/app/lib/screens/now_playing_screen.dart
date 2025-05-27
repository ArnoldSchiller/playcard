// lib/screens/now_playing_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:media_kit_video/media_kit_video.dart'; // Für Video-Wiedergabe

import 'package:playcard_app/config/constants.dart';
import 'package:playcard_app/providers/search_provider.dart';
import 'package:playcard_app/providers/media_player_provider.dart'; // NEU: Importiere den MediaPlayerProvider
import 'package:playcard_app/widgets/playcard_app_bar.dart';

class NowPlayingScreen extends StatefulWidget {
  const NowPlayingScreen({
    super.key,
  });

  @override
  State<NowPlayingScreen> createState() => _NowPlayingScreenState();
}

class _NowPlayingScreenState extends State<NowPlayingScreen> {
  @override
  Widget build(BuildContext context) {
    // Watch the SearchProvider for the search bar
    final searchProvider = context.watch<SearchProvider>();
    // Watch the MediaPlayerProvider for current song and player state
    final mediaPlayerProvider = context.watch<MediaPlayerProvider>();
    ////print('DBG: RadioStatusScreen canPop(): ${Navigator.of(context).canPop()}');

    // Wenn kein Song spielt, zeige eine Meldung oder gehe zurück
    if (mediaPlayerProvider.currentSong == null) {
      return Scaffold(
        appBar: PlaycardAppBar(
          title: kAppName, // App-Name aus Constants
          searchController: searchProvider.searchController,
          onSearchChanged: (text) {}, // Logik im SearchProvider
          hintText: 'Search songs, artists, or genres...',
        ),
        body: const Center(
          child: Text('No song is currently playing.'),
        ),
      );
    }

    // Wenn ein Song spielt, zeige den Now Playing Screen
    return Scaffold(
      appBar: PlaycardAppBar(
        title: mediaPlayerProvider.currentSong!.name, // Titel ist der Song-Name
        searchController: searchProvider.searchController,
        onSearchChanged: (text) {
          // Wenn der Benutzer etwas in die Suche eingibt, navigiere zurück zum Hauptscreen
          if (text.isNotEmpty && Navigator.of(context).canPop()) {
            Navigator.of(context).pop();
          }
        },
        hintText: 'Search songs, artists, or genres...',
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Video-Anzeige, wenn es ein Video ist
            if (mediaPlayerProvider.hasVideo && mediaPlayerProvider.videoController != null)
              Expanded(
                child: Stack(
                  children: [
                    AspectRatio(
                      aspectRatio: 16 / 9, // Oder ein anderes passendes Seitenverhältnis
                      child: Video(controller: mediaPlayerProvider.videoController!),
                    ),
                    Positioned(
                      top: 16,
                      right: 16,
                      child: IconButton(
                        icon: const Icon(Icons.close, color: Colors.white),
                        onPressed: () {
                          Navigator.of(context).pop(); // zurück zum Hauptscreen
                        },
                      ),
                    ),
                  ],
                ),
              )
            else // Ansonsten Cover-Bild oder Musik-Icon
              Column(
                children: [
                  // Cover-Bild
                  mediaPlayerProvider.currentSong!.coverImageUrl != null && mediaPlayerProvider.currentSong!.coverImageUrl!.isNotEmpty
                      ? Image.network(
                          mediaPlayerProvider.currentSong!.coverImageUrl!,
                          width: MediaQuery.of(context).size.width * 0.8, // 80% der Breite
                          height: MediaQuery.of(context).size.width * 0.8,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) =>
                              Image.asset(
                                kLogo, // Dein Standard-Icon
                                width: MediaQuery.of(context).size.width * 0.3,
                                height: MediaQuery.of(context).size.width * 0.3,
                                fit: BoxFit.contain,
                              ),
                        )
                      : Image.asset(
                          kLogo, // Dein Standard-Icon
                          width: MediaQuery.of(context).size.width * 0.3,
                          height: MediaQuery.of(context).size.width * 0.3,
                          fit: BoxFit.contain,
                        ),
                  const SizedBox(height: 20),
                  Text(
                    mediaPlayerProvider.currentSong!.name,
                    style: Theme.of(context).textTheme.headlineSmall,
                    textAlign: TextAlign.center,
                  ),
                  Text(
                    mediaPlayerProvider.currentSong!.artist ?? 'Unknown Artist',
                    style: Theme.of(context).textTheme.titleMedium,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            const SizedBox(height: 20),
            // Player Controls
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  icon: const Icon(Icons.skip_previous, size: 48),
                  onPressed: () {
                    // TODO: Implement previous song logic
                  },
                ),
                IconButton(
                  icon: Icon(mediaPlayerProvider.isPlaying ? Icons.pause_circle_filled : Icons.play_circle_filled, size: 64),
                  onPressed: () {
                    mediaPlayerProvider.playOrPause();
                  },
                ),
                IconButton(
                  icon: const Icon(Icons.skip_next, size: 48),
                  onPressed: () {
                    // TODO: Implement next song logic
                  },
                ),
              ],
            ),
            // Fortschrittsbalken (optional, kann später hinzugefügt werden)
            // Slider(
            //   min: 0,
            //   max: mediaPlayerProvider.currentDuration.inSeconds.toDouble(),
            //   value: mediaPlayerProvider.currentPosition.inSeconds.toDouble(),
            //   onChanged: (value) {
            //     mediaPlayerProvider.player?.seek(Duration(seconds: value.toInt()));
            //   },
            // ),
          ],
        ),
      ),
    );
  }
}

