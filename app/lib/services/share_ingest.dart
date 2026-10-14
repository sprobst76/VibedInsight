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
