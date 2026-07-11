import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../config/app_settings.dart';
import '../database/app_database.dart';
import '../repositories/items_repository.dart';

/// Overridden in main.dart with the settings loaded from SharedPreferences.
/// Updating this provider's state rebuilds the API client and everything
/// that depends on it.
final appSettingsProvider = StateProvider<AppSettings>((ref) {
  throw UnimplementedError('appSettingsProvider must be overridden in main');
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final settings = ref.watch(appSettingsProvider);
  return ApiClient(baseUrl: settings.serverUrl, apiKey: settings.apiKey);
});

final appDatabaseProvider = Provider<AppDatabase>((ref) {
  final db = AppDatabase();
  ref.onDispose(() => db.close());
  return db;
});

final itemsRepositoryProvider = Provider<ItemsRepository>((ref) {
  final api = ref.watch(apiClientProvider);
  final db = ref.watch(appDatabaseProvider);
  final repo = ItemsRepository(api, db);
  ref.onDispose(() => repo.dispose());
  return repo;
});

/// Stream provider for online status
final onlineStatusProvider = StreamProvider<bool>((ref) {
  final repo = ref.watch(itemsRepositoryProvider);
  return repo.onlineStatus;
});

/// Provider for current online status (non-stream)
final isOnlineProvider = Provider<bool>((ref) {
  final repo = ref.watch(itemsRepositoryProvider);
  return repo.isOnline;
});
