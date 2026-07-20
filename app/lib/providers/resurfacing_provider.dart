import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../models/content_item.dart';
import '../services/notification_service.dart';
import 'api_provider.dart';

/// Holds the current "rediscovered" item (or null). Fetched once per app
/// session; shows a local notification at most once per day.
class ResurfacingNotifier extends StateNotifier<ContentItem?> {
  ResurfacingNotifier(this._api, this._notifications) : super(null);

  final ApiClient _api;
  final NotificationService _notifications;
  bool _loaded = false;

  static const _lastShownKey = 'resurface_last_shown';

  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    try {
      final item = await _api.getResurfacing();
      if (item == null) return;
      state = item;
      await _maybeNotify(item);
    } catch (_) {
      // Serendipity is best-effort — never surface an error to the user.
    }
  }

  void dismiss() => state = null;

  Future<void> _maybeNotify(ContentItem item) async {
    final prefs = await SharedPreferences.getInstance();
    final today = DateTime.now().toIso8601String().substring(0, 10);
    if (prefs.getString(_lastShownKey) == today) return; // already shown today
    await prefs.setString(_lastShownKey, today);
    await _notifications.showResurfacing(
      title: item.displayTitle,
      itemId: item.id,
    );
  }
}

final resurfacingProvider =
    StateNotifierProvider<ResurfacingNotifier, ContentItem?>((ref) {
  return ResurfacingNotifier(
    ref.watch(apiClientProvider),
    ref.watch(notificationServiceProvider),
  );
});
