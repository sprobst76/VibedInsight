import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notifications =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

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
    // Handle notification tap - could navigate to item detail
    // The payload contains the item ID if available
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
