import '../api/api_client.dart';
import '../models/content_item.dart';
import '../repositories/items_repository.dart';

/// How long the share path waits for the server before falling back to the
/// offline queue (the app is about to close, so we must not wait longer).
const shareIngestTimeout = Duration(seconds: 4);

enum ShareOutcomeKind { saved, queued, rejected, failed }

class ShareOutcome {
  final ShareOutcomeKind kind;
  final ContentItem? item;
  final String? message;

  const ShareOutcome(this.kind, {this.item, this.message});
}

/// Ingest a shared URL through the repository (offline queue aware).
/// Never throws; the result tells the caller which notification to show.
Future<ShareOutcome> ingestSharedUrl(
  ItemsRepository repo,
  String url, {
  Duration timeout = shareIngestTimeout,
}) async {
  try {
    final result = await repo.ingestUrl(url, timeout: timeout);
    if (result.isPending) return const ShareOutcome(ShareOutcomeKind.queued);
    return ShareOutcome(ShareOutcomeKind.saved, item: result.item);
  } on IngestRejectedException catch (e) {
    return ShareOutcome(ShareOutcomeKind.rejected, message: e.message);
  } catch (e) {
    return ShareOutcome(ShareOutcomeKind.failed, message: e.toString());
  }
}

/// Title for a note created from shared text without a URL: first non-empty
/// line, cut to ~60 characters.
String noteTitleFromText(String text, String fallback) {
  final line = text
      .split('\n')
      .map((l) => l.trim())
      .firstWhere((l) => l.isNotEmpty, orElse: () => '');
  if (line.isEmpty) return fallback;
  return line.length <= 60 ? line : '${line.substring(0, 60).trimRight()}...';
}

/// Ingest shared text that contains no URL as a note.
Future<ShareOutcome> ingestSharedNote(
  ItemsRepository repo,
  String text, {
  required String fallbackTitle,
  Duration timeout = shareIngestTimeout,
}) async {
  try {
    final result = await repo.ingestNote(
      title: noteTitleFromText(text, fallbackTitle),
      text: text.trim(),
      timeout: timeout,
    );
    if (result.isPending) return const ShareOutcome(ShareOutcomeKind.queued);
    return ShareOutcome(ShareOutcomeKind.saved, item: result.item);
  } catch (e) {
    return ShareOutcome(ShareOutcomeKind.failed, message: e.toString());
  }
}
