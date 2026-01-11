import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../database/app_database.dart';
import '../repositories/items_repository.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient();
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
