// lib/models/song.dart
// KEIN Import von 'package:playcard_app/config/constants.dart' hier!

class Song {
  final String name;
  final String? artist;
  final String? relativePath;
  final String streamUrl;
  final String? coverImageUrl;

  Song({
    required this.name,
    this.artist,
    this.relativePath,
    required this.streamUrl,
    this.coverImageUrl,
  });

  // KORREKTUR: baseUrl Parameter komplett entfernt
  // Die baseUrl wird jetzt an der Aufrufstelle gehandhabt, nicht hier im Model.
  factory Song.fromJson(Map<String, dynamic> json) {
    final bool isRadioStream = json.containsKey('mount_point') && (json['mount_point'] as String).isNotEmpty;

    // calculatedStreamUrl muss an der Aufrufstelle mit der baseUrl kombiniert werden,
    // wenn es sich nicht um einen Radio-Stream handelt, der eine komplette URL liefert.
    // Das Model selbst sollte keine Kenntnis von kBaseUrl haben.
    String calculatedStreamUrl;
    if (isRadioStream) {
      calculatedStreamUrl = json['mount_point']?.toString() ?? '';
    } else {
      // Für Suchergebnisse wird hier nur der relative Pfad gespeichert.
      // Die vollständige URL wird dann an der Stelle gebildet, wo Song.fromJson aufgerufen wird.
      calculatedStreamUrl = json['relative_path']?.toString() ?? '';
    }

    String? title = json['title']?.toString();
    String? artist = json['artist']?.toString();

    if (isRadioStream && (title?.startsWith('http://') == true || title?.startsWith('https://') == true)) {
      title = json['server_title']?.toString() ?? json['mount_point']?.toString() ?? 'Live Stream';
    } else if (isRadioStream && title?.contains(' - https://') == true) {
        final parts = title!.split(' - https://');
        if (parts.isNotEmpty) {
            title = parts[0].trim();
        }
    }

    return Song(
      name: title ?? json['mount_point']?.toString() ?? json['relative_path']?.toString() ?? 'Unbekannter Song',
      artist: artist,
      relativePath: json['relative_path']?.toString(),
      streamUrl: calculatedStreamUrl, // Dies ist hier der relative Pfad oder die volle Mount-Point-URL
      coverImageUrl: json['cover_image_url']?.toString(),
    );
  }
}
