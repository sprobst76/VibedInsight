import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';

import '../services/notification_service.dart';
import 'api_provider.dart';
import 'items_provider.dart';

/// Tracks if app was launched from share intent
bool _launchedFromShare = false;
bool get wasLaunchedFromShare => _launchedFromShare;

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
  final Ref _ref;
  StreamSubscription? _subscription;

  ShareIntentNotifier(this._ref) : super(null) {
    _init();
  }

  void _init() {
    // Handle shared content when app is opened from share
    ReceiveSharingIntent.instance.getInitialMedia().then((value) {
      if (value.isNotEmpty) {
        _launchedFromShare = true;
        _handleSharedFiles(value, closeAfter: true);
      }
    });

    // Handle shared content when app is already running
    _subscription = ReceiveSharingIntent.instance.getMediaStream().listen(
      (value) {
        if (value.isNotEmpty) {
          _handleSharedFiles(value, closeAfter: false);
        }
      },
      onError: (err) {
        // Handle errors silently
      },
    );
  }

  void _handleSharedFiles(List<SharedMediaFile> files, {bool closeAfter = false}) {
    for (final file in files) {
      if (file.type == SharedMediaType.text || file.type == SharedMediaType.url) {
        // Try to find URL in either path or message
        // Chrome shares URL in path, other apps might use message
        final combinedText = '${file.path ?? ''} ${file.message ?? ''}';
        final content = SharedContent(text: combinedText);
        final url = content.extractUrl();

        if (url != null) {
          _processUrlInBackground(url, closeAfter: closeAfter);
        }
        break;
      }
    }
    // Reset immediately - we don't need UI to handle it
    ReceiveSharingIntent.instance.reset();
  }

  Future<void> _processUrlInBackground(String url, {bool closeAfter = false}) async {
    final notificationService = _ref.read(notificationServiceProvider);
    final apiClient = _ref.read(apiClientProvider);

    // Show "processing" notification
    await notificationService.showProcessingStarted(url);

    // Close app immediately if launched from share intent
    // The processing continues in the background
    if (closeAfter) {
      // Small delay to ensure notification is shown
      await Future.delayed(const Duration(milliseconds: 100));
      SystemNavigator.pop();
    }

    try {
      // Ingest the URL
      final item = await apiClient.ingestUrl(url);

      // Update items list if provider is active
      try {
        _ref.read(itemsProvider.notifier).updateItem(item);
      } catch (_) {
        // Provider might not be active yet
      }

      // Show success notification
      await notificationService.showProcessingComplete(
        title: item.displayTitle,
        itemId: item.id,
      );
    } catch (e) {
      // Show error notification
      await notificationService.showProcessingFailed(url, e.toString());
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
  return ShareIntentNotifier(ref);
});
