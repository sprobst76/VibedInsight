import 'package:drift/drift.dart';

/// Cached content items from the API
class CachedItems extends Table {
  IntColumn get id => integer()();
  TextColumn get contentType => text()();
  TextColumn get status => text()();
  TextColumn get url => text().nullable()();
  TextColumn get title => text().nullable()();
  TextColumn get source => text().nullable()();
  TextColumn get summary => text().nullable()();
  BoolColumn get isFavorite => boolean().withDefault(const Constant(false))();
  BoolColumn get isRead => boolean().withDefault(const Constant(false))();
  BoolColumn get isArchived => boolean().withDefault(const Constant(false))();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime().nullable()();
  DateTimeColumn get processedAt => dateTime().nullable()();
  DateTimeColumn get cachedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Cached topics
class CachedTopics extends Table {
  IntColumn get id => integer()();
  TextColumn get name => text()();
  DateTimeColumn get createdAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Junction table for item-topic relationship
class CachedItemTopics extends Table {
  IntColumn get itemId => integer().references(CachedItems, #id)();
  IntColumn get topicId => integer().references(CachedTopics, #id)();

  @override
  Set<Column> get primaryKey => {itemId, topicId};
}

/// Pending actions queue for offline operations
class PendingActions extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get actionType => text()(); // 'favorite', 'read', 'archive', 'delete', 'ingest_url', 'ingest_note'
  IntColumn get itemId => integer().nullable()(); // For existing items
  TextColumn get payload => text().nullable()(); // JSON payload for create actions
  DateTimeColumn get createdAt => dateTime()();
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
}

/// Sync metadata
class SyncMetadata extends Table {
  TextColumn get key => text()();
  TextColumn get value => text()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {key};
}
