// lib/widgets/current_track_display.dart
import 'package:flutter/material.dart';
import 'package:playcard_app/config/constants.dart'; // Bleibt hier, falls nötig für Song-Typ
import 'package:playcard_app/models/song.dart'; // Bleibt hier, falls nötig für Song-Typ

class CurrentTrackDisplay extends StatelessWidget {
  final List<Map<String, dynamic>> rawRadioStreams;
  final Function(Map<String, dynamic> streamData) onPlayStream;

  const CurrentTrackDisplay({
    super.key,
    required this.rawRadioStreams,
    required this.onPlayStream,
  });

  @override
  Widget build(BuildContext context) {
    if (rawRadioStreams.isEmpty) {
      return const Center(child: Text('Keine Radiostreams verfügbar.'));
    }

    return ListView.builder(
      itemCount: rawRadioStreams.length,
      itemBuilder: (context, index) {
        final stream = rawRadioStreams[index];

        final String artist = stream['artist']?.toString() ?? 'N/A';
        String title = stream['title']?.toString() ?? 'N/A';
        final String serverTitle = stream['server_title']?.toString() ?? 'Unbekannter Stream';
        final String streamUrl = stream['mount_point']?.toString() ?? ''; // Die tatsächliche Stream URL

        String displayTitle = title;
        if (displayTitle.startsWith('http://') || displayTitle.startsWith('https://')) {
          displayTitle = serverTitle;
        } else if (displayTitle.contains(' - https://')) {
            final parts = displayTitle.split(' - https://');
            if (parts.isNotEmpty) {
                displayTitle = parts[0].trim();
            }
        }

        // KORREKTUR: Verwende hier Card und ListTile für bessere Optik und Klickbarkeit
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
          child: ListTile(
            leading: const Icon(Icons.radio), // Oder ein Radio-Icon
            title: Text(serverTitle), // Haupttitel des Senders
            subtitle: Text('Aktuell spielt: $artist - $displayTitle'), // Aktueller Track
            trailing: IconButton(
              icon: const Icon(Icons.play_circle_fill, size: 36),
              onPressed: () => onPlayStream(stream), // Rufe den Callback auf
            ),
            onTap: () => onPlayStream(stream), // Auch der gesamte Listeneintrag ist klickbar
          ),
        );
      },
    );
  }
}
