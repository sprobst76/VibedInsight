import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

import '../models/content_item.dart';
import 'tables.dart';

part 'app_database.g.dart';

@DriftDatabase(tables: [
  CachedItems,
  CachedTopics,
  CachedItemTopics,
  PendingActions,
  SyncMetadata,
])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  // ============================================================
  // Items Cache Operations
  // ============================================================

  /// Cache items from API response
  Future<void> cacheItems(List<ContentItem> items) async {
    await batch((batch) {
      for (final item in items) {
        // Upsert item
        batch.insert(
          cachedItems,
          CachedItemsCompanion.insert(
            id: Value(item.id),
            contentType: item.contentType.name,
            status: item.status.name,
            url: Value(item.url),
            title: Value(item.title),
            source: Value(item.source),
            summary: Value(item.summary),
            isFavorite: Value(item.isFavorite),
            isRead: Value(item.isRead),
            isArchived: Value(item.isArchived),
            createdAt: item.createdAt,
            updatedAt: Value(item.updatedAt),
            processedAt: Value(item.processedAt),
            cachedAt: DateTime.now(),
          ),
          mode: InsertMode.insertOrReplace,
        );

        // Cache topics and relations
        for (final topic in item.topics) {
          batch.insert(
            cachedTopics,
            CachedTopicsCompanion.insert(
              id: Value(topic.id),
              name: topic.name,
              createdAt: topic.createdAt,
            ),
            mode: InsertMode.insertOrReplace,
          );
          batch.insert(
            cachedItemTopics,
            CachedItemTopicsCompanion.insert(
              itemId: item.id,
              topicId: topic.id,
            ),
            mode: InsertMode.insertOrReplace,
          );
        }
      }
    });
  }

  /// Get cached items with optional filters
  Future<List<ContentItem>> getCachedItems({
    String? search,
    int? topicId,
    bool? favoritesOnly,
    bool? unreadOnly,
    bool? archivedOnly,
    SortField sortBy = SortField.date,
    SortOrder sortOrder = SortOrder.desc,
    int page = 1,
    int pageSize = 20,
  }) async {
    var query = select(cachedItems);

    // Apply filters
    query = query..where((t) {
      Expression<bool> condition = const Constant(true);

      if (search != null && search.isNotEmpty) {
        final searchPattern = '%$search%';
        condition = condition &
          (t.title.like(searchPattern) | t.summary.like(searchPattern));
      }

      if (favoritesOnly == true) {
        condition = condition & t.isFavorite.equals(true);
      }

      if (unreadOnly == true) {
        condition = condition & t.isRead.equals(false);
      }

      if (archivedOnly == true) {
        condition = condition & t.isArchived.equals(true);
      } else {
        // By default, don't show archived
        condition = condition & t.isArchived.equals(false);
      }

      return condition;
    });

    // Topic filter requires a subquery
    if (topicId != null) {
      final itemsWithTopic = selectOnly(cachedItemTopics)
        ..addColumns([cachedItemTopics.itemId])
        ..where(cachedItemTopics.topicId.equals(topicId));

      query = query..where((t) => t.id.isInQuery(itemsWithTopic));
    }

    // Sorting
    switch (sortBy) {
      case SortField.date:
        query = query..orderBy([
          (t) => sortOrder == SortOrder.desc
              ? OrderingTerm.desc(t.createdAt)
              : OrderingTerm.asc(t.createdAt)
        ]);
      case SortField.title:
        query = query..orderBy([
          (t) => sortOrder == SortOrder.desc
              ? OrderingTerm.desc(t.title)
              : OrderingTerm.asc(t.title)
        ]);
      case SortField.status:
        query = query..orderBy([
          (t) => sortOrder == SortOrder.desc
              ? OrderingTerm.desc(t.status)
              : OrderingTerm.asc(t.status)
        ]);
    }

    // Pagination
    query = query..limit(pageSize, offset: (page - 1) * pageSize);

    final rows = await query.get();

    // Fetch topics for each item
    final result = <ContentItem>[];
    for (final row in rows) {
      final topics = await _getTopicsForItem(row.id);
      result.add(_rowToContentItem(row, topics));
    }

    return result;
  }

  /// Get count of cached items (for pagination)
  Future<int> getCachedItemsCount({
    String? search,
    int? topicId,
    bool? favoritesOnly,
    bool? unreadOnly,
    bool? archivedOnly,
  }) async {
    final countExp = cachedItems.id.count();
    var query = selectOnly(cachedItems)..addColumns([countExp]);

    query = query..where(
      cachedItems.isArchived.equals(archivedOnly ?? false) &
      (favoritesOnly == true ? cachedItems.isFavorite.equals(true) : const Constant(true)) &
      (unreadOnly == true ? cachedItems.isRead.equals(false) : const Constant(true))
    );

    if (search != null && search.isNotEmpty) {
      final searchPattern = '%$search%';
      query = query..where(
        cachedItems.title.like(searchPattern) | cachedItems.summary.like(searchPattern)
      );
    }

    final result = await query.getSingle();
    return result.read(countExp) ?? 0;
  }

  Future<List<Topic>> _getTopicsForItem(int itemId) async {
    final query = select(cachedTopics).join([
      innerJoin(
        cachedItemTopics,
        cachedItemTopics.topicId.equalsExp(cachedTopics.id),
      ),
    ])..where(cachedItemTopics.itemId.equals(itemId));

    final rows = await query.get();
    return rows.map((row) {
      final topic = row.readTable(cachedTopics);
      return Topic(
        id: topic.id,
        name: topic.name,
        createdAt: topic.createdAt,
      );
    }).toList();
  }

  ContentItem _rowToContentItem(CachedItem row, List<Topic> topics) {
    return ContentItem(
      id: row.id,
      contentType: ContentType.fromString(row.contentType),
      status: ProcessingStatus.fromString(row.status),
      url: row.url,
      title: row.title,
      source: row.source,
      summary: row.summary,
      isFavorite: row.isFavorite,
      isRead: row.isRead,
      isArchived: row.isArchived,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
      processedAt: row.processedAt,
      topics: topics,
    );
  }

  /// Update a single cached item's flags
  Future<void> updateItemFlags(int itemId, {
    bool? isFavorite,
    bool? isRead,
    bool? isArchived,
  }) async {
    await (update(cachedItems)..where((t) => t.id.equals(itemId))).write(
      CachedItemsCompanion(
        isFavorite: isFavorite != null ? Value(isFavorite) : const Value.absent(),
        isRead: isRead != null ? Value(isRead) : const Value.absent(),
        isArchived: isArchived != null ? Value(isArchived) : const Value.absent(),
      ),
    );
  }

  /// Delete a cached item
  Future<void> deleteCachedItem(int itemId) async {
    await (delete(cachedItemTopics)..where((t) => t.itemId.equals(itemId))).go();
    await (delete(cachedItems)..where((t) => t.id.equals(itemId))).go();
  }

  /// Clear all cached items
  Future<void> clearCache() async {
    await delete(cachedItemTopics).go();
    await delete(cachedItems).go();
    await delete(cachedTopics).go();
  }

  // ============================================================
  // Topics Cache Operations
  // ============================================================

  /// Get all cached topics
  Future<List<Topic>> getCachedTopics() async {
    final rows = await select(cachedTopics).get();
    return rows.map((row) => Topic(
      id: row.id,
      name: row.name,
      createdAt: row.createdAt,
    )).toList();
  }

  /// Cache topics from API
  Future<void> cacheTopics(List<Topic> topics) async {
    await batch((batch) {
      for (final topic in topics) {
        batch.insert(
          cachedTopics,
          CachedTopicsCompanion.insert(
            id: Value(topic.id),
            name: topic.name,
            createdAt: topic.createdAt,
          ),
          mode: InsertMode.insertOrReplace,
        );
      }
    });
  }

  // ============================================================
  // Pending Actions (Offline Queue)
  // ============================================================

  /// Add a pending action
  Future<int> addPendingAction(String actionType, {int? itemId, Map<String, dynamic>? payload}) async {
    return into(pendingActions).insert(
      PendingActionsCompanion.insert(
        actionType: actionType,
        itemId: Value(itemId),
        payload: Value(payload != null ? jsonEncode(payload) : null),
        createdAt: DateTime.now(),
      ),
    );
  }

  /// Get all pending actions
  Future<List<PendingAction>> getPendingActions() async {
    return (select(pendingActions)..orderBy([(t) => OrderingTerm.asc(t.createdAt)])).get();
  }

  /// Remove a pending action (after successful sync)
  Future<void> removePendingAction(int id) async {
    await (delete(pendingActions)..where((t) => t.id.equals(id))).go();
  }

  /// Increment retry count for a pending action
  Future<void> incrementRetryCount(int id) async {
    await customStatement(
      'UPDATE pending_actions SET retry_count = retry_count + 1 WHERE id = ?',
      [id],
    );
  }

  /// Check if there are pending actions
  Future<bool> hasPendingActions() async {
    final count = await (selectOnly(pendingActions)..addColumns([pendingActions.id.count()])).getSingle();
    return (count.read(pendingActions.id.count()) ?? 0) > 0;
  }

  // ============================================================
  // Sync Metadata
  // ============================================================

  /// Get last sync time
  Future<DateTime?> getLastSyncTime() async {
    final result = await (select(syncMetadata)..where((t) => t.key.equals('last_sync'))).getSingleOrNull();
    if (result != null) {
      return DateTime.tryParse(result.value);
    }
    return null;
  }

  /// Set last sync time
  Future<void> setLastSyncTime(DateTime time) async {
    await into(syncMetadata).insert(
      SyncMetadataCompanion.insert(
        key: 'last_sync',
        value: time.toIso8601String(),
        updatedAt: DateTime.now(),
      ),
      mode: InsertMode.insertOrReplace,
    );
  }
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'vibedinsight.db'));
    return NativeDatabase.createInBackground(file);
  });
}
