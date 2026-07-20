class ApiConfig {
  // Default server URL used until the user configures one in Settings.
  // Self-hosted: change this or set your URL in the app's settings screen.
  static const String defaultUrl = 'https://insight.lab.halbewahrheit21.de';

  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 30);

  /// Items fetched per page. The inbox loads pages incrementally as the user
  /// scrolls (see ItemsNotifier.loadItems + InboxScreen._onScroll), so the
  /// list stays smooth regardless of archive size.
  static const int pageSize = 20;
}
