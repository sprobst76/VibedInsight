import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart' show Locale, WidgetsBinding;
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';

import '../l10n/app_localizations.dart';
import '../services/notification_service.dart';
import '../services/share_ingest.dart';
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
        debugPrint('ShareIntent stream error: $err');
        final notificationService = _ref.read(notificationServiceProvider);
        notificationService.showShareStatus(
          title: 'Share Intent',
          body: err.toString(),
          error: true,
        );
      },
    );
  }

  void _handleSharedFiles(List<SharedMediaFile> files, {bool closeAfter = false}) {
    for (final file in files) {
      if (file.type == SharedMediaType.text || file.type == SharedMediaType.url) {
        // Try to find URL in either path or message
        // Chrome shares URL in path, other apps might use message
        final combinedText = '${file.path} ${file.message ?? ''}';
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
    final repo = _ref.read(itemsRepositoryProvider);
    final lang = WidgetsBinding.instance.platformDispatcher.locale.languageCode;
    final l10n = lookupAppLocalizations(Locale(lang == 'de' ? 'de' : 'en'));
    final domain = Uri.tryParse(url)?.host ?? url;

    // Wait for the ingest (short timeout, queue fallback) BEFORE closing the
    // app, otherwise the request may be lost once the activity is gone.
    final outcome = await ingestSharedUrl(repo, url);
    await _notify(notificationService, l10n, outcome, domain);

    if (outcome.item != null) {
      try {
        _ref.read(itemsProvider.notifier).updateItem(outcome.item!);
      } catch (_) {
        // Provider might not be active yet
      }
    }

    if (closeAfter) {
      // Small delay to ensure the notification is shown
      await Future.delayed(const Duration(milliseconds: 100));
      SystemNavigator.pop();
    }
  }

  Future<void> _notify(
    NotificationService service,
    AppLocalizations l10n,
    ShareOutcome outcome,
    String target,
  ) {
    switch (outcome.kind) {
      case ShareOutcomeKind.saved:
        return service.showShareStatus(
          title: l10n.shareSavedTitle,
          body: outcome.item?.displayTitle ?? target,
          itemId: outcome.item?.id,
        );
      case ShareOutcomeKind.queued:
        return service.showShareStatus(
          title: l10n.shareQueuedTitle,
          body: l10n.shareQueuedBody(target),
        );
      case ShareOutcomeKind.rejected:
        return service.showShareStatus(
          title: l10n.shareRejectedTitle,
          body: outcome.message ?? target,
          error: true,
        );
      case ShareOutcomeKind.failed:
        return service.showShareStatus(
          title: l10n.shareFailedTitle,
          body: l10n.shareFailedBody(target),
          error: true,
        );
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
