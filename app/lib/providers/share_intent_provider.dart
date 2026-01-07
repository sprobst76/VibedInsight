import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';

class SharedContent {
  final String? text;
  final String? url;

  SharedContent({this.text, this.url});

  /// Extract URL from shared text
  String? extractUrl() {
    if (url != null) return url;
    if (text == null) return null;

    // Try to find URL in text
    final urlRegex = RegExp(
      r'https?://[^\s<>"{}|\\^`\[\]]+',
      caseSensitive: false,
    );
    final match = urlRegex.firstMatch(text!);
    return match?.group(0);
  }

  bool get hasUrl => extractUrl() != null;
}

class ShareIntentNotifier extends StateNotifier<SharedContent?> {
  StreamSubscription? _subscription;

  ShareIntentNotifier() : super(null) {
    _init();
  }

  void _init() {
    // Handle shared content when app is opened from share
    ReceiveSharingIntent.instance.getInitialMedia().then((value) {
      if (value.isNotEmpty) {
        _handleSharedFiles(value);
      }
    });

    // Handle shared content when app is already running
    _subscription = ReceiveSharingIntent.instance.getMediaStream().listen(
      (value) {
        if (value.isNotEmpty) {
          _handleSharedFiles(value);
        }
      },
      onError: (err) {
        // Handle errors
      },
    );
  }

  void _handleSharedFiles(List<SharedMediaFile> files) {
    for (final file in files) {
      if (file.type == SharedMediaType.text || file.type == SharedMediaType.url) {
        state = SharedContent(
          text: file.message,
          url: file.path.startsWith('http') ? file.path : null,
        );
        break;
      }
    }
  }

  void clear() {
    state = null;
    ReceiveSharingIntent.instance.reset();
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }
}

final shareIntentProvider =
    StateNotifierProvider<ShareIntentNotifier, SharedContent?>((ref) {
  return ShareIntentNotifier();
});
