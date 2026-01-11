import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../api/api_client.dart';
import '../database/app_database.dart';
import '../models/content_item.dart';

/// Repository that handles online/offline data access for items.
///
/// Strategy:
/// - Online-first: Try API first, cache results
/// - Offline fallback: Return cached data if API fails
/// - Write-through: Actions are queued and synced when online
class ItemsRepository {
  final ApiClient _api;
  final AppDatabase _db;

  bool _isOnline = true;
  final _onlineStatusController = StreamController<bool>.broadcast();

  ItemsRepository(this._api, this._db);

  /// Stream of online status changes
  Stream<bool> get onlineStatus => _onlineStatusController.stream;

  /// Current online status
  bool get isOnline => _isOnline;

  /// Check connectivity and update status
  Future<bool> checkConnectivity() async {
    try {
      final result = await _api.healthCheck();
      _updateOnlineStatus(result);
      return result;
    } catch (e) {
      _updateOnlineStatus(false);
      return false;
    }
  }

  void _updateOnlineStatus(bool status) {
    if (_isOnline != status) {
      _isOnline = status;
      _onlineStatusController.add(status);
    }
  }

  /// Get items with online-first strategy
  Future<ItemsResult> getItems({
    int page = 1,
    int pageSize = 20,
    int? topicId,
    String? search,
    bool favoritesOnly = false,
    bool unreadOnly = false,
    bool archivedOnly = false,
    SortField sortBy = SortField.date,
    SortOrder sortOrder = SortOrder.desc,
  }) async {
    try {
      // Try online first
      final result = await _api.getItems(
        page: page,
        pageSize: pageSize,
        topicId: topicId,
        search: search,
        favoritesOnly: favoritesOnly,
        unreadOnly: unreadOnly,
        archivedOnly: archivedOnly,
        sortBy: sortBy,
        sortOrder: sortOrder,
      );

      _updateOnlineStatus(true);

      // Cache the results
      await _db.cacheItems(result.items);
      await _db.setLastSyncTime(DateTime.now());

      return ItemsResult(
        items: result.items,
        total: result.total,
        page: result.page,
        pageSize: result.pageSize,
        pages: result.pages,
        isFromCache: false,
      );
    } on DioException catch (e) {
      // Network error - fall back to cache
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        return _getFromCache(
          page: page,
          pageSize: pageSize,
          topicId: topicId,
          search: search,
          favoritesOnly: favoritesOnly,
          unreadOnly: unreadOnly,
          archivedOnly: archivedOnly,
          sortBy: sortBy,
          sortOrder: sortOrder,
        );
      }
      rethrow;
    }
  }

  Future<ItemsResult> _getFromCache({
    int page = 1,
    int pageSize = 20,
    int? topicId,
    String? search,
    bool? favoritesOnly,
    bool? unreadOnly,
    bool? archivedOnly,
    SortField sortBy = SortField.date,
    SortOrder sortOrder = SortOrder.desc,
  }) async {
    final items = await _db.getCachedItems(
      page: page,
      pageSize: pageSize,
      topicId: topicId,
      search: search,
      favoritesOnly: favoritesOnly,
      unreadOnly: unreadOnly,
      archivedOnly: archivedOnly,
      sortBy: sortBy,
      sortOrder: sortOrder,
    );

    final total = await _db.getCachedItemsCount(
      topicId: topicId,
      search: search,
      favoritesOnly: favoritesOnly,
      unreadOnly: unreadOnly,
      archivedOnly: archivedOnly,
    );

    final pages = (total / pageSize).ceil();

    return ItemsResult(
      items: items,
      total: total,
      page: page,
      pageSize: pageSize,
      pages: pages,
      isFromCache: true,
    );
  }

  /// Toggle favorite with offline support
  Future<ContentItem> toggleFavorite(int itemId, bool currentValue) async {
    // Optimistically update local cache
    await _db.updateItemFlags(itemId, isFavorite: !currentValue);

    try {
      final result = await _api.toggleFavorite(itemId);
      _updateOnlineStatus(true);
      await _db.updateItemFlags(itemId, isFavorite: result.isFavorite);
      return result;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        // Queue for later sync
        await _db.addPendingAction('toggle_favorite', itemId: itemId);
        // Return optimistic result
        return ContentItem(
          id: itemId,
          contentType: ContentType.link,
          status: ProcessingStatus.pending,
          isFavorite: !currentValue,
          createdAt: DateTime.now(),
        );
      }
      // Revert on non-network error
      await _db.updateItemFlags(itemId, isFavorite: currentValue);
      rethrow;
    }
  }

  /// Toggle read with offline support
  Future<ContentItem> toggleRead(int itemId, bool currentValue) async {
    await _db.updateItemFlags(itemId, isRead: !currentValue);

    try {
      final result = await _api.toggleRead(itemId);
      _updateOnlineStatus(true);
      await _db.updateItemFlags(itemId, isRead: result.isRead);
      return result;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        await _db.addPendingAction('toggle_read', itemId: itemId);
        return ContentItem(
          id: itemId,
          contentType: ContentType.link,
          status: ProcessingStatus.pending,
          isRead: !currentValue,
          createdAt: DateTime.now(),
        );
      }
      await _db.updateItemFlags(itemId, isRead: currentValue);
      rethrow;
    }
  }

  /// Toggle archive with offline support
  Future<ContentItem> toggleArchive(int itemId, bool currentValue) async {
    await _db.updateItemFlags(itemId, isArchived: !currentValue);

    try {
      final result = await _api.toggleArchive(itemId);
      _updateOnlineStatus(true);
      await _db.updateItemFlags(itemId, isArchived: result.isArchived);
      return result;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        await _db.addPendingAction('toggle_archive', itemId: itemId);
        return ContentItem(
          id: itemId,
          contentType: ContentType.link,
          status: ProcessingStatus.pending,
          isArchived: !currentValue,
          createdAt: DateTime.now(),
        );
      }
      await _db.updateItemFlags(itemId, isArchived: currentValue);
      rethrow;
    }
  }

  /// Delete item with offline support
  Future<void> deleteItem(int itemId) async {
    await _db.deleteCachedItem(itemId);

    try {
      await _api.deleteItem(itemId);
      _updateOnlineStatus(true);
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        await _db.addPendingAction('delete', itemId: itemId);
        return;
      }
      rethrow;
    }
  }

  /// Ingest URL with offline support
  Future<IngestResult> ingestUrl(String url) async {
    try {
      final result = await _api.ingestUrl(url);
      _updateOnlineStatus(true);
      return IngestResult(item: result, isPending: false);
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        await _db.addPendingAction('ingest_url', payload: {'url': url});
        return IngestResult(item: null, isPending: true);
      }
      rethrow;
    }
  }

  /// Ingest note with offline support
  Future<IngestResult> ingestNote({
    required String title,
    required String text,
  }) async {
    try {
      final result = await _api.ingestText(title: title, text: text);
      _updateOnlineStatus(true);
      return IngestResult(item: result, isPending: false);
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        await _db.addPendingAction('ingest_note', payload: {
          'title': title,
          'text': text,
        });
        return IngestResult(item: null, isPending: true);
      }
      rethrow;
    }
  }

  /// Get topics with caching
  Future<TopicsResult> getTopics() async {
    try {
      final topics = await _api.getTopics();
      _updateOnlineStatus(true);
      await _db.cacheTopics(topics);
      return TopicsResult(topics: topics, isFromCache: false);
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        _updateOnlineStatus(false);
        final cached = await _db.getCachedTopics();
        return TopicsResult(topics: cached, isFromCache: true);
      }
      rethrow;
    }
  }

  /// Sync pending actions when back online
  Future<SyncResult> syncPendingActions() async {
    final actions = await _db.getPendingActions();
    if (actions.isEmpty) {
      return SyncResult(synced: 0, failed: 0);
    }

    int synced = 0;
    int failed = 0;

    for (final action in actions) {
      try {
        await _executePendingAction(action);
        await _db.removePendingAction(action.id);
        synced++;
      } catch (e) {
        await _db.incrementRetryCount(action.id);
        failed++;
      }
    }

    return SyncResult(synced: synced, failed: failed);
  }

  Future<void> _executePendingAction(PendingAction action) async {
    switch (action.actionType) {
      case 'toggle_favorite':
        await _api.toggleFavorite(action.itemId!);
      case 'toggle_read':
        await _api.toggleRead(action.itemId!);
      case 'toggle_archive':
        await _api.toggleArchive(action.itemId!);
      case 'delete':
        await _api.deleteItem(action.itemId!);
      case 'ingest_url':
        final payload = jsonDecode(action.payload!) as Map<String, dynamic>;
        await _api.ingestUrl(payload['url'] as String);
      case 'ingest_note':
        final payload = jsonDecode(action.payload!) as Map<String, dynamic>;
        await _api.ingestText(
          title: payload['title'] as String,
          text: payload['text'] as String,
        );
    }
  }

  /// Check if there are pending actions
  Future<bool> hasPendingActions() => _db.hasPendingActions();

  /// Get last sync time
  Future<DateTime?> getLastSyncTime() => _db.getLastSyncTime();

  /// Clear all cached data
  Future<void> clearCache() => _db.clearCache();

  bool _isNetworkError(DioException e) {
    return e.type == DioExceptionType.connectionTimeout ||
           e.type == DioExceptionType.receiveTimeout ||
           e.type == DioExceptionType.sendTimeout ||
           e.type == DioExceptionType.connectionError ||
           e.type == DioExceptionType.unknown;
  }

  void dispose() {
    _onlineStatusController.close();
  }
}

/// Result wrapper for items with cache indicator
class ItemsResult {
  final List<ContentItem> items;
  final int total;
  final int page;
  final int pageSize;
  final int pages;
  final bool isFromCache;

  ItemsResult({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.pages,
    required this.isFromCache,
  });
}

/// Result wrapper for topics with cache indicator
class TopicsResult {
  final List<Topic> topics;
  final bool isFromCache;

  TopicsResult({required this.topics, required this.isFromCache});
}

/// Result wrapper for ingest operations
class IngestResult {
  final ContentItem? item;
  final bool isPending;

  IngestResult({required this.item, required this.isPending});
}

/// Result of sync operation
class SyncResult {
  final int synced;
  final int failed;

  SyncResult({required this.synced, required this.failed});
}
