import 'package:shared_preferences/shared_preferences.dart';

import 'api_config.dart';

/// Persisted connection settings: server URL and API key.
///
/// Loaded once at app start (see main.dart); changes via [save] update
/// SharedPreferences and the in-memory values used to rebuild the API client.
class AppSettings {
  AppSettings({required this.serverUrl, required this.apiKey});

  static const _keyServerUrl = 'server_url';
  static const _keyApiKey = 'api_key';

  final String serverUrl;
  final String apiKey;

  static Future<AppSettings> load() async {
    final prefs = await SharedPreferences.getInstance();
    return AppSettings(
      serverUrl: prefs.getString(_keyServerUrl) ?? ApiConfig.defaultUrl,
      apiKey: prefs.getString(_keyApiKey) ?? '',
    );
  }

  static Future<AppSettings> save({
    required String serverUrl,
    required String apiKey,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final normalizedUrl = serverUrl.trim().replaceAll(RegExp(r'/+$'), '');
    await prefs.setString(_keyServerUrl, normalizedUrl);
    await prefs.setString(_keyApiKey, apiKey.trim());
    return AppSettings(serverUrl: normalizedUrl, apiKey: apiKey.trim());
  }
}
