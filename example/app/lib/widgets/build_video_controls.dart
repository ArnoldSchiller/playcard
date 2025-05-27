// lib/widgets/build_video_controls.dart
/*
*To use:
*import 'package:playcard_app/widgets/build_video_controls.dart';
*showModalBottomSheet(
*  context: context,
*  builder: (context) => const VideoControls(),
*);
*/

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:playcard_app/providers/media_player_provider.dart';

class VideoControls extends StatefulWidget {
  const VideoControls({super.key});

  @override
  State<VideoControls> createState() => _VideoControlsState();
}

class _VideoControlsState extends State<VideoControls> {
  double _progress = 0.3; // Beispielwert, kannst du dynamisch setzen

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<MediaPlayerProvider>();

    return Container(
      color: Colors.black54,
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Steuerelemente
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              IconButton(
                icon: const Icon(Icons.skip_previous, color: Colors.white),
                onPressed: () {/* Vorheriger Titel */},
              ),
              IconButton(
                icon: Icon(
                  provider.isPlaying ? Icons.pause : Icons.play_arrow,
                  color: Colors.white,
                  size: 36,
                ),
                onPressed: () => provider.playOrPause(),
              ),
              IconButton(
                icon: const Icon(Icons.skip_next, color: Colors.white),
                onPressed: () {/* Nächster Titel */},
              ),
              IconButton(
                icon: const Icon(Icons.fullscreen_exit, color: Colors.white),
                onPressed: () {
                  Navigator.pop(context);
                  provider.stop();
                },
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Fortschrittsanzeige
          Slider(
            value: _progress,
            onChanged: (value) {
              setState(() {
                _progress = value;
              });
              // Hier: provider.seekTo(value) oder so etwas einbauen
            },
            activeColor: Colors.white,
            inactiveColor: Colors.white24,
          ),
        ],
      ),
    );
  }
}

