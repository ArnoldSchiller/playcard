// lib/widgets/radio_streams_list.dart
import 'package:flutter/material.dart';
import 'package:playcard_app/models/song.dart';
import 'package:playcard_app/widgets/current_track_display.dart';
import 'package:playcard_app/config/constants.dart'; // <-- Bleibt drin, falls benötigt!

class RadioStreamsList extends StatefulWidget {
  final Future<List<Map<String, dynamic>>> radioStreamsFuture;
  final Function(Song song) onPlayStream;

  const RadioStreamsList({
    super.key,
    required this.radioStreamsFuture,
    required this.onPlayStream,
  });

  @override
  State<RadioStreamsList> createState() => _RadioStreamsListState();
}

class _RadioStreamsListState extends State<RadioStreamsList> {

  Song _createSongFromRadioStream(Map<String, dynamic> streamData) {
    // Song.fromJson ohne baseUrl Parameter aufrufen.
    // Für Radio-Streams enthält streamData['mount_point'] bereits die komplette URL,
    // daher ist keine kBaseUrl-Kombination im Model oder hier nötig.
    final song = Song.fromJson(streamData);

    // KORREKTUR: Das Cover-Bild könnte auch relativ sein, also hier prüfen und die URL vervollständigen.
    String? finalCoverImageUrl = song.coverImageUrl;
    if (song.coverImageUrl != null && song.coverImageUrl!.isNotEmpty && !song.coverImageUrl!.startsWith('http')) {
      finalCoverImageUrl = '$kBaseUrl${song.coverImageUrl}';
    }

    // Erstelle einen neuen Song mit der korrigierten Cover-URL
    return Song(
      name: song.name,
      artist: song.artist,
      relativePath: song.relativePath,
      streamUrl: song.streamUrl, // Die ist bei Radio-Streams schon korrekt
      coverImageUrl: finalCoverImageUrl,
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: widget.radioStreamsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        } else if (snapshot.hasError) {
          return Center(child: Text('Fehler beim Laden der Radiostreams: ${snapshot.error}'));
        } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const Center(child: Text('Keine Radiostreams verfügbar.'));
        } else {
          return CurrentTrackDisplay(
            rawRadioStreams: snapshot.data!,
            onPlayStream: (streamData) {
              final songToPlay = _createSongFromRadioStream(streamData);
              widget.onPlayStream(songToPlay);
            },
          );
        }
      },
    );
  }
}
