// lib/widgets/search_results_list.dart
import 'package:playcard_app/config/constants.dart';
import 'package:flutter/material.dart';
import 'package:playcard_app/models/song.dart';

class SearchResultsList extends StatelessWidget {
  final List<Song> searchResults;
  final bool isLoadingSearch;
  final String? errorMessageSearch;
  final Function(Song song) onSongTap; // Callback zum Abspielen

  const SearchResultsList({
    super.key,
    required this.searchResults,
    required this.isLoadingSearch,
    this.errorMessageSearch,
    required this.onSongTap,
  });

  @override
  Widget build(BuildContext context) {
    if (isLoadingSearch) {
      return const Center(child: CircularProgressIndicator());
    } else if (errorMessageSearch != null) {
      return Center(child: Text('Fehler bei der Suche: $errorMessageSearch'));
    } else if (searchResults.isEmpty) {
      return const Center(child: Text('Keine Suchergebnisse gefunden.'));
    } else {
      return ListView.builder(
        itemCount: searchResults.length,
        itemBuilder: (context, index) {
          final song = searchResults[index];
          return Card(
            margin: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
            child: ListTile(
              leading: song.coverImageUrl != null && song.coverImageUrl!.isNotEmpty
                  ? Image.network(
                      song.coverImageUrl!,
                      width: 50,
                      height: 50,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) => const Icon(Icons.music_note),
                    )
                  : const Icon(Icons.music_note),
              title: Text(song.name),
              subtitle: Text(song.artist ?? song.relativePath ?? ''),
              onTap: () => onSongTap(song),
            ),
          );
        },
      );
    }
  }
}
