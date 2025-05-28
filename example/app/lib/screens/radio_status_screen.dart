// lib/screens/radio_status_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:playcard_app/config/constants.dart';
import 'package:playcard_app/models/song.dart';
import 'package:playcard_app/services/api_service.dart';
import 'package:playcard_app/screens/now_playing_screen.dart';

import 'package:playcard_app/providers/search_provider.dart';
import 'package:playcard_app/providers/media_player_provider.dart'; // <--- NEW IMPORT
import 'package:playcard_app/widgets/search_results_list.dart';
import 'package:playcard_app/widgets/radio_streams_list.dart';
import 'package:playcard_app/widgets/playcard_app_bar.dart';

import 'package:url_launcher/url_launcher.dart'; // Fallback url_launcher
import 'package:media_kit_video/media_kit_video.dart'; // <--- NEW IMPORT for Video playback

// launchAudio is a fall back don't remove this
Future<void> _launchAudio(String url, BuildContext context) async {
  if (url.isNotEmpty && Uri.tryParse(url)?.isAbsolute == true) {
    if (await canLaunchUrl(Uri.parse(url))) {
      await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open URL: $url')), // Geändert auf Englisch
        );
      }
    }
  } else {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid URL to open.')), // Geändert auf Englisch
      );
    }
  }
}

class RadioStatusScreen extends StatefulWidget {
  const RadioStatusScreen({super.key});

  @override
  State<RadioStatusScreen> createState() => _RadioStatusScreenState();
}

class _RadioStatusScreenState extends State<RadioStatusScreen> {
  final ApiService _apiService = ApiService();

  // NO LONGER NEEDED: final GlobalKey<RadioMediaPlayerState> _mediaPlayerKey = GlobalKey<RadioMediaPlayerState>();
  // NO LONGER NEEDED: Song? _currentPlayingSong; // State for the currently playing song (now in Provider)




  late Future<List<Map<String, dynamic>>> _radioStreamsFuture;

  @override
  void initState() {
    super.initState();
    _radioStreamsFuture = _fetchRadioStreams();
  }

  Future<List<Map<String, dynamic>>> _fetchRadioStreams() async {
    try {
      final response = await _apiService.fetchRadioStatus();
      final List<dynamic> rawStreams = response['radio_streams'] ?? [];
      return List<Map<String, dynamic>>.from(rawStreams);
    } catch (e) {
      ////print('Fehler beim Laden der Radio-Streams: $e');
      throw Exception('Fehler beim Laden der Radio-Streams: $e');
    }
  }

  
  void _playSong(Song song) {
    ////print('Attempting to play song: ${song.name} from URL: ${song.streamUrl}');

    if (song.streamUrl.isEmpty || Uri.tryParse(song.streamUrl)?.isAbsolute == false) {
      ////print('ERROR: Invalid or empty stream URL: ${song.streamUrl}');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Invalid stream URL for this song.')),
        );
      }
      return;
    }

    // Access the MediaPlayerProvider and call its play method
    final mediaPlayerProvider = context.read<MediaPlayerProvider>();
    mediaPlayerProvider.play(song);

    ////print('Song successfully sent to internal player.');

    // Only navigate to NowPlayingScreen if the search is empty
    // or if the user explicitly clicks on it (from the global player bar).
    // Search should remain on this screen.
    final searchProvider = context.read<SearchProvider>(); // Use read here as we're just calling a method
    if (searchProvider.searchController.text.isEmpty && !Navigator.of(context).canPop()) {
        Navigator.of(context).pushAndRemoveUntil(
  	MaterialPageRoute(
    		builder: (_) => NowPlayingScreen(),
    		fullscreenDialog: true,
  		),
  		(route) => route.isFirst, // Behalte nur den Home-Screen im Stack
	);
	/*
	Navigator.of(context).push(
        MaterialPageRoute(
  		builder: (_) => NowPlayingScreen(),
  		fullscreenDialog: true, // <- Wichtig für modales Verhalten
  
  
          
         ),
        );
        */
     bool canPop = ModalRoute.of(context)?.isFirst ?? false;
    }
  }
 
 @override
 Widget build(BuildContext context) {
  //Watch Provider
  final searchProvider = context.watch<SearchProvider>();
  final mediaPlayerProvider = context.watch<MediaPlayerProvider>();

  return WillPopScope(
    onWillPop: () async {
      if (mediaPlayerProvider.hasVideo) {
        mediaPlayerProvider.stop();
        return true;
      }
      return !Navigator.of(context).canPop();
    },
    child: Scaffold(
      appBar: PlaycardAppBar(
              title: kAppName,
              searchController: searchProvider.searchController,
              onSearchChanged: (text) {},
              hintText: 'Search songs, artists, or genres...',
            ),
      body: Stack(
        children: [
          Column(
            children: [
              Expanded(
                child: searchProvider.isSearching &&
                        searchProvider.searchResults.isNotEmpty
                    ? SearchResultsList(
                        searchResults: searchProvider.searchResults,
                        isLoadingSearch: searchProvider.isLoadingSearch,
                        errorMessageSearch: searchProvider.errorMessageSearch,
                        onSongTap: _playSong,
                      )
                    : (searchProvider.isSearching &&
                            searchProvider.searchResults.isEmpty &&
                            !searchProvider.isLoadingSearch)
                        ? const Center(child: Text('No search results found.'))
                        : RadioStreamsList(
                            radioStreamsFuture: _radioStreamsFuture,
                            onPlayStream: _playSong,
                          ),
              ),
              if (mediaPlayerProvider.currentSong != null)
                Material(
                  elevation: 8.0,
                  child: Container(
                    color: Theme.of(context).cardColor,
                    padding: const EdgeInsets.all(8.0),
                    child: Row(
                      children: [
                        mediaPlayerProvider.currentSong!.coverImageUrl != null &&
                                mediaPlayerProvider
                                    .currentSong!.coverImageUrl!.isNotEmpty
                            ? Image.network(
                                mediaPlayerProvider
                                    .currentSong!.coverImageUrl!,
                                width: 50,
                                height: 50,
                                fit: BoxFit.cover,
                                errorBuilder:
                                    (context, error, stackTrace) =>
                                        const Icon(Icons.music_note, size: 50),
                              )
                            : const Icon(Icons.music_note, size: 50),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                mediaPlayerProvider.currentSong!.name,
                                style:
                                    Theme.of(context).textTheme.titleMedium,
                                overflow: TextOverflow.ellipsis,
                              ),
                              Text(
                                mediaPlayerProvider.currentSong!.artist ??
                                    'Unknown Artist',
                                style:
                                    Theme.of(context).textTheme.bodySmall,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.skip_previous),
                          onPressed: () {
                            mediaPlayerProvider.stop();
                            Navigator.pop(context);
                          },
                        ),
                        IconButton(
                          icon: Icon(mediaPlayerProvider.isPlaying
                              ? Icons.pause
                              : Icons.play_arrow),
                          onPressed: () {
                            mediaPlayerProvider.playOrPause();
                          },
                        ),
                        IconButton(
                          icon: const Icon(Icons.skip_next),
                          onPressed: () {
                            // TODO: Play next song
                          },
                        ),
                        IconButton(
                          icon: const Icon(Icons.open_in_full),
                          onPressed: () {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (context) => NowPlayingScreen(),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
          /**
          if (mediaPlayerProvider.hasVideo && mediaPlayerProvider.videoController != null)
            Positioned.fill(
              child: Stack(
                children: [
                  Video(controller: mediaPlayerProvider.videoController!),
                  Positioned(
                    top: MediaQuery.of(context).padding.top + 10,
                    left: 10,
                    child: Material(
                      color: Colors.transparent,
                      child: IconButton(
                        icon: Icon(Icons.close, color: Colors.white),
                        onPressed: () {
                          mediaPlayerProvider.resetPlayer();
                          Navigator.popUntil(
                              context, (route) => route.isFirst);
                        },
                      ),
                    ),
                  ),
                  Positioned.fill(
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onTap: () {
                        showModalBottomSheet(
                          context: context,
                          builder: (context) => NowPlayingScreen(),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          **/
            
        ],
      ),
    ),
  );
//End Widget
 }



//End Class
}
