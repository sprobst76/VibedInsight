import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notifications =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  /// Called with the notification payload when the user taps a notification
  /// while the app is running. Set by main() to route via the app router.
  void Function(String payload)? onSelectPayload;

  Future<void> initialize() async {
    if (_initialized) return;

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: false,
    );

    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _notifications.initialize(
      settings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    // Request permissions on Android 13+
    await _notifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();

    _initialized = true;
  }

  void _onNotificationTapped(NotificationResponse response) {
    final payload = response.payload;
    if (payload != null && payload.isNotEmpty) {
      onSelectPayload?.call(payload);
    }
  }

  /// Payload the app was launched with by tapping a notification (cold start),
  /// or null if it wasn't launched from a notification.
  Future<String?> launchPayload() async {
    final details = await _notifications.getNotificationAppLaunchDetails();
    if (details?.didNotificationLaunchApp ?? false) {
      return details?.notificationResponse?.payload;
    }
    return null;
  }

  /// Show a "rediscovered" notification for an old, unread item.
  Future<void> showResurfacing({
    required String title,
    required int itemId,
  }) async {
    await _notifications.show(
      _generateId(),
      'Wiederentdeckt',
      title,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'resurfacing',
          'Wiederentdeckt',
          channelDescription: 'Alte, ungelesene Einträge zum Wiederentdecken',
          importance: Importance.defaultImportance,
          priority: Priority.defaultPriority,
          icon: '@mipmap/ic_launcher',
        ),
        iOS: DarwinNotificationDetails(),
      ),
      payload: itemId.toString(),
    );
  }

  /// Show a notification that URL processing has started
  Future<void> showProcessingStarted(String url) async {
    final domain = Uri.tryParse(url)?.host ?? url;

    await _notifications.show(
      _generateId(),
      'Adding to VibedInsight',
      'Processing: $domain',
      _processingDetails(),
    );
  }

  /// Show a notification that processing completed successfully
  Future<void> showProcessingComplete({
    required String title,
    required int itemId,
  }) async {
    await _notifications.show(
      _generateId(),
      'Added to VibedInsight',
      title,
      _successDetails(),
      payload: itemId.toString(),
    );
  }

  /// Show a notification that processing failed
  Future<void> showProcessingFailed(String url, String? error) async {
    final domain = Uri.tryParse(url)?.host ?? url;

    await _notifications.show(
      _generateId(),
      'Failed to add',
      'Could not process: $domain',
      _errorDetails(),
    );
  }

  /// Show notification when weekly summary is ready
  Future<void> showWeeklySummaryReady({
    required String tldr,
    required int weekId,
  }) async {
    await _notifications.show(
      weekId,
      'Deine Woche auf einen Blick',
      tldr.length > 100 ? '${tldr.substring(0, 100)}...' : tldr,
      _weeklySummaryDetails(),
      payload: 'weekly:$weekId',
    );
  }

  NotificationDetails _weeklySummaryDetails() {
    return const NotificationDetails(
      android: AndroidNotificationDetails(
        'weekly_summary',
        'Wochenzusammenfassung',
        channelDescription: 'Benachrichtigungen zu Wochenzusammenfassungen',
        importance: Importance.high,
        priority: Priority.high,
        icon: '@mipmap/ic_launcher',
      ),
      iOS: DarwinNotificationDetails(),
    );
  }

  /// Show ongoing progress notification
  Future<void> showProgress({
    required int id,
    required String title,
    required int progress,
    required int maxProgress,
  }) async {
    await _notifications.show(
      id,
      title,
      'Processing...',
      NotificationDetails(
        android: AndroidNotificationDetails(
          'processing',
          'Processing',
          channelDescription: 'Content processing notifications',
          importance: Importance.low,
          priority: Priority.low,
          showProgress: true,
          maxProgress: maxProgress,
          progress: progress,
          ongoing: true,
          autoCancel: false,
        ),
      ),
    );
  }

  Future<void> cancel(int id) async {
    await _notifications.cancel(id);
  }

  NotificationDetails _processingDetails() {
    return const NotificationDetails(
      android: AndroidNotificationDetails(
        'processing',
        'Processing',
        channelDescription: 'Content processing notifications',
        importance: Importance.low,
        priority: Priority.low,
        ongoing: true,
        autoCancel: false,
        icon: '@mipmap/ic_launcher',
      ),
      iOS: DarwinNotificationDetails(),
    );
  }

  NotificationDetails _successDetails() {
    return const NotificationDetails(
      android: AndroidNotificationDetails(
        'success',
        'Success',
        channelDescription: 'Success notifications',
        importance: Importance.defaultImportance,
        priority: Priority.defaultPriority,
        icon: '@mipmap/ic_launcher',
      ),
      iOS: DarwinNotificationDetails(),
    );
  }

  NotificationDetails _errorDetails() {
    return const NotificationDetails(
      android: AndroidNotificationDetails(
        'error',
        'Errors',
        channelDescription: 'Error notifications',
        importance: Importance.high,
        priority: Priority.high,
        icon: '@mipmap/ic_launcher',
      ),
      iOS: DarwinNotificationDetails(),
    );
  }

  int _generateId() => DateTime.now().millisecondsSinceEpoch.remainder(100000);
}

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService();
});
