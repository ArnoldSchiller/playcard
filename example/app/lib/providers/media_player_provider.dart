// lib/providers/media_player_provider.dart
import 'package:flutter/foundation.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';
import 'package:playcard_app/config/constants.dart';
import 'package:playcard_app/models/song.dart';

class MediaPlayerProvider extends ChangeNotifier {
  Player? _player;
  VideoController? _videoController;
  Song? _currentSong;
  bool _isPlaying = false;
  Duration _currentPosition = Duration.zero;
  Duration _currentDuration = Duration.zero;
  bool _isBuffering = false;
  bool _hasVideo = false;

  Player? get player => _player;
  VideoController? get videoController => _videoController;

  Song? get currentSong => _currentSong;
  bool get isPlaying => _isPlaying;
  Duration get currentPosition => _currentPosition;
  Duration get currentDuration => _currentDuration;
  bool get isBuffering => _isBuffering;
  bool get hasVideo => _hasVideo;

  MediaPlayerProvider() {
    _player = Player();
    _player!.stream.playing.listen((isPlaying) {
      _isPlaying = isPlaying;
      notifyListeners();
    });
    _player!.stream.position.listen((position) {
      _currentPosition = position;
      notifyListeners();
    });
    _player!.stream.duration.listen((duration) {
      _currentDuration = duration;
      notifyListeners();
    });
    _player!.stream.buffering.listen((isBuffering) {
      _isBuffering = isBuffering;
      notifyListeners();
    });
    _player!.stream.error.listen((error) {
      ////print('MediaPlayerProvider Error: $error');
    });
  }

  Future<void> play(Song song) async {
    if (_player == null) {
      ////print('Error: Player not initialized.');
      return;
    }

    _currentSong = song;
    _hasVideo = song.streamUrl.endsWith('.mp4');

    if (_hasVideo && _videoController == null) {
      _videoController = VideoController(_player!);
    } else if (!_hasVideo && _videoController != null) {
      // Wenn wir von Video zu Audio wechseln, setzen wir den VideoController auf null
      // und erwarten, dass er bei Bedarf neu erstellt wird.
      // KEIN _videoController?.dispose() hier!
      _videoController = null;
    }

    notifyListeners();

    ////print('Playing: ${song.name} - URL: ${song.streamUrl}');
    await _player!.open(Media(song.streamUrl));
    _player!.play();
  }

  Future<void> playOrPause() async {
    if (_player != null) {
      await _player!.playOrPause();
    }
  }

  Future<void> stop() async {
    if (_player != null) {
      await _player!.stop();
      _currentSong = null;
      _isPlaying = false;
      _currentPosition = Duration.zero;
      _currentDuration = Duration.zero;
      _isBuffering = false;
      _hasVideo = false;
      notifyListeners();
    }
  }

  Future<void> resetPlayer() async {
      if (_player != null) {
	await _player!.dispose();
       _currentSong = null;
       _isPlaying = false;
       _hasVideo = false;
       // Nicht: _videoController?.dispose();
       _videoController = null; // Das reicht in der neuen Version
       notifyListeners();
      }
   }

  @override
  void dispose() {
    _player?.dispose();
    // KEIN _videoController?.dispose() hier! Der VideoController wird mit dem Player disposed.
    super.dispose();
    ////print('MediaPlayerProvider disposed.');
  }
}
