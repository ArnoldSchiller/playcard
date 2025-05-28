// lib/services/api_service.dart

import 'package:playcard_app/config/constants.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Exception-Klasse für sauberere Fehlerausgabe
class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => 'ApiException: $message';
}

/// Zentrale Service-Klasse für alle API-Aufrufe
class ApiService {
  ApiService(); // Konstruktor ohne 'const'

  final String kApiUrl = '$kBaseUrl/api';

  /// Allgemeine GET-Methode, die JSON zurückliefert
  /// Diese Methode ist primär für Endpunkte gedacht, die eine Map zurückgeben.
  Future<Map<String, dynamic>> _getJson(String endpoint) async {
    final uri = Uri.parse('$kApiUrl/$endpoint');
    final response = await http.get(uri);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      if (data is Map<String, dynamic>) {
        return data;
      } else {
        // Dieser Fall sollte nicht eintreten, wenn _getJson nur für Map-Responses gedacht ist.
        // Falls ein Endpunkt hier eine Liste zurückgibt, muss man ihn anders behandeln.
        throw ApiException('Unerwartetes Format für $endpoint: Erwartet Map, bekam ${data.runtimeType}. Inhalt: ${response.body}');
      }
    } else {
      throw ApiException('Fehler beim Laden von $endpoint: ${response.statusCode}. Details: ${response.body}');
    }
  }

  // Diese Methode wird jetzt zu fetchIndex zusammengeführt, um Redundanz zu vermeiden.
  // Future<List<Map<String, dynamic>>> fetchFlatIndex({String? search}) async {
  //   return fetchIndex(structured: false, search: search);
  // }

  // Diese Methode wird jetzt zu fetchIndex zusammengeführt, um Redundanz zu vermeiden.
  // Future<List<Map<String, dynamic>>> fetchStructuredIndex({String? search}) async {
  //   return fetchIndex(structured: true, search: search);
  // }

  /// 🔊 Holt den aktuellen Status des Radios
  Future<Map<String, dynamic>> fetchRadioStatus() => _getJson('radio');

  /// 🎵 Holt die Trackliste
  ///
  /// Wenn [structured] true ist, bekommst du eine Ordnerstruktur (die "data" Liste aus der Map).
  /// Wenn [structured] false ist, bekommst du eine flache Liste der "files".
  /// Diese Methode kann nun direkt eine flache Liste oder eine Liste von Ordnern liefern,
  /// abhängig von der API-Antwort.
  Future<List<Map<String, dynamic>>> fetchIndex({
    required bool structured, // 'structured' ist jetzt notwendig, um die erwartete Antwort zu steuern
    String? search,
  }) async {
    final params = <String>[];

    params.add('structured=${structured ? 1 : 0}');
    if (search != null && search.trim().isNotEmpty) {
      params.add('search=${Uri.encodeComponent(search)}');
    }

    final query = params.isNotEmpty ? '?${params.join('&')}' : '';
    final response = await http.get(Uri.parse('$kApiUrl/index$query'));

    if (response.statusCode == 200) {
      final decodedData = jsonDecode(response.body);

      // --- WICHTIG: Hier prüfen wir beide mögliche Antwortstrukturen! ---
      if (decodedData is List<dynamic>) {
        // Fall 1: Die API gibt direkt eine flache Liste von Dateien zurück (wie im Fehlerbild gezeigt)
        // Dies sollte der Fall sein, wenn structured=0 und/oder search verwendet wird und die API direkt die Files liefert.
        return List<Map<String, dynamic>>.from(decodedData);
      } else if (decodedData is Map<String, dynamic> && decodedData.containsKey('data')) {
        // Fall 2: Die API gibt eine Map mit einem 'data'-Schlüssel zurück, der eine Liste enthält
        // Dies sollte der Fall sein, wenn structured=1 oder wenn die API immer eine Wrapper-Map sendet.
        final List<dynamic> rawDataList = decodedData['data'] as List<dynamic>;

        if (structured) {
          // Wenn der Aufrufer eine strukturierte Liste wollte, gib die 'data'-Liste zurück
          return List<Map<String, dynamic>>.from(rawDataList);
        } else {
          // Wenn der Aufrufer eine flache Liste wollte, flache die 'files' aus den Ordnern
          List<Map<String, dynamic>> flatTracks = [];
          for (var folderItem in rawDataList) {
            if (folderItem is Map<String, dynamic> && folderItem.containsKey('files')) {
              final List<dynamic> rawFilesList = folderItem['files'] as List<dynamic>;
              flatTracks.addAll(List<Map<String, dynamic>>.from(rawFilesList));
            }
          }
          return flatTracks;
        }
      } else {
        // Wenn keines der erwarteten Formate zutrifft
        throw ApiException('Unerwartetes Format bei fetchIndex: Weder Liste noch Map mit "data" Schlüssel. Bekam ${decodedData.runtimeType}. Inhalt: ${response.body}');
      }
    } else {
      throw ApiException('Fehler beim Laden des Index: ${response.statusCode}. Details: ${response.body}');
    }
  }

  /// ❓ Holt Details zu einem bestimmten Track
  ///
  /// [title] ist der relative Pfad zur Datei, z. B. "Rock/Queen - Bohemian.mp3"
  Future<Map<String, dynamic>> fetchTrackInfo(String title) async {
    final encodedTitle = Uri.encodeComponent(title);
    return _getJson('track_info?title=$encodedTitle');
  }

  /// 🔀 Holt einen zufälligen Track
  Future<Map<String, dynamic>> fetchRandomTrack() => _getJson('random_track');

  /// 🧪 API-Einstiegsbeschreibung
  Future<Map<String, dynamic>> fetchApiOverview() => _getJson('');
}
