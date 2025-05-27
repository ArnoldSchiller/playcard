// lib/widgets/playcard_app_bar.dart

import 'package:flutter/material.dart';

class PlaycardAppBar extends StatelessWidget implements PreferredSizeWidget {
  final TextEditingController searchController;
  final Function(String) onSearchChanged;
  final String title;
  final String hintText; // <<< NEUER PARAMETER HIER

  const PlaycardAppBar({
    super.key,
    required this.searchController,
    required this.onSearchChanged,
    this.title = 'Playcard',
    this.hintText = 'Suchen...', // <<< STANDARDWERT, falls nicht übergeben
  });

  @override
  Widget build(BuildContext context) {
    return AppBar(
      title: Text(title),
      backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(kToolbarHeight),
        child: Padding(
          padding: const EdgeInsets.all(8.0),
          child: TextField(
            controller: searchController,
            onChanged: onSearchChanged,
            decoration: InputDecoration(
              hintText: hintText, // <<< HIER WIRD DER PARAMETER VERWENDET
              // ... (restliche InputDecoration Einstellungen) ...
            ),
          ),
        ),
      ),
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight * 2);
}
