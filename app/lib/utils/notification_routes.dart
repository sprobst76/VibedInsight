/// Map a notification payload to an app route, or null when it maps to none.
///
/// Payload conventions (set in [NotificationService]):
/// - `weekly:<id>`      -> the weekly digest screen
/// - `<int>` (item id)  -> that item's detail screen
String? notificationRoute(String? payload) {
  if (payload == null || payload.isEmpty) return null;
  if (payload.startsWith('weekly:')) return '/weekly';
  final id = int.tryParse(payload);
  if (id != null) return '/item/$id';
  return null;
}
