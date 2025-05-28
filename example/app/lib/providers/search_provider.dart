// lib/providers/search_provider.dart
import 'package:flutter/material.dart';
import 'package:playcard_app/models/song.dart';
import 'package:playcard_app/services/api_service.dart';
import 'package:playcard_app/config/constants.dart';

class SearchProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();
  final TextEditingController searchController = TextEditingController();

  List<Song> _searchResults = [];
  bool _isLoadingSearch = false;
  String? _errorMessageSearch;

  List<Song> get searchResults => _searchResults;
  bool get isLoadingSearch => _isLoadingSearch;
  String? get errorMessageSearch => _errorMessageSearch;
  bool get isSearching => searchController.text.isNotEmpty;

  SearchProvider() {
    searchController.addListener(_onSearchQueryChanged);
  }

  void _onSearchQueryChanged() {
    if (searchController.text.isNotEmpty) {
      _performSearch(searchController.text);
    } else {
      _searchResults = [];
      _isLoadingSearch = false;
      _errorMessageSearch = null;
      notifyListeners();
    }
  }

  Future<void> _performSearch(String query) async {
    _isLoadingSearch = true;
    _errorMessageSearch = null;
    notifyListeners();
    ////print('SearchProvider: Starte Suche für Query: "$query"');

    try {
      final results = await _apiService.fetchIndex(search: query, structured: false);
      if (results != null) {
        _searchResults = results.map((json) {
          final song = Song.fromJson(json);

          String finalStreamUrl = song.streamUrl;
          String? finalCoverImageUrl = song.coverImageUrl;

          // **KORREKTUR FÜR URL-AUFBAU**
          // Prüfen, ob die URL bereits absolut ist (beginnt mit http/https)
          // Wenn nicht, dann hänge kBaseUrl davor.

          // Für Stream-URL
          if (finalStreamUrl.isNotEmpty && !finalStreamUrl.startsWith('http')) {
            // Wenn der Pfad relativ ist und mit '/' beginnt, ist die Konkatenation direkt:
            // kBaseUrl (ohne abschließenden Slash) + /Pfad (mit führendem Slash) -> korrekt
            finalStreamUrl = kBaseUrl + finalStreamUrl;
          }
          // Wenn relativePath existiert und streamUrl *dennoch* relativ ist, könnte es eine alternative URL sein.
          // Wir priorisieren hier die streamUrl, da sie direkt zum Abspielen verwendet wird.
          // Optional könnten Sie hier komplexere Logik einfügen, falls relativePath immer die Quelle sein sollte.
          // Für jetzt gehen wir davon aus, dass `song.streamUrl` das ist, was abgespielt werden soll.


          // Für Cover-Image-URL
          if (finalCoverImageUrl != null && finalCoverImageUrl.isNotEmpty && !finalCoverImageUrl.startsWith('http')) {
            finalCoverImageUrl = kBaseUrl + finalCoverImageUrl;
          }
          // Wenn das Cover-Image eine externe, absolute URL ist (z.B. von jaquearnoux.de),
          // dann wollen wir kBaseUrl NICHT davor setzen.
          // Die ursprüngliche Prüfung `!finalCoverImageUrl!.startsWith('http')` fängt das bereits ab,
          // daher wird bei "https://jaquearnoux.de/radio.png" kein kBaseUrl davor gesetzt.


          ////print('SearchProvider: Verarbeite Song "${song.name}"');
          ////print('  Original streamUrl: ${song.streamUrl}');
          ////print('  Relative path: ${song.relativePath}'); // Dieser Wert wird nicht mehr direkt zum Bauen genutzt, aber zur Info
          ////print('  Final streamUrl: $finalStreamUrl');
          ////print('  Final coverImageUrl: $finalCoverImageUrl');


          return Song(
            name: song.name,
            artist: song.artist,
            relativePath: song.relativePath,
            streamUrl: finalStreamUrl,
            coverImageUrl: finalCoverImageUrl,
          );
        }).toList();
        ////print('SearchProvider: ${searchResults.length} Suchergebnisse gefunden.');
      } else {
        _searchResults = [];
        ////print('SearchProvider: Keine Suchergebnisse zurückbekommen.');
      }
      _errorMessageSearch = null;
    } catch (e) {
      _errorMessageSearch = 'Fehler bei der Suche: $e';
      _searchResults = [];
      ////print('SearchProvider: FEHLER bei der Suche: $e');
    } finally {
      _isLoadingSearch = false;
      notifyListeners();
    }
  }

  void triggerSearch() {
    if (searchController.text.isNotEmpty) {
      _performSearch(searchController.text);
    }
  }

  void clearSearch() {
    searchController.clear();
  }

  @override
  void dispose() {
    searchController.removeListener(_onSearchQueryChanged);
    searchController.dispose();
    super.dispose();
  }
}
