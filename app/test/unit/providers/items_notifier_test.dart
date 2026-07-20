import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/database/app_database.dart';
import 'package:vibedinsight/providers/api_provider.dart';
import 'package:vibedinsight/providers/items_provider.dart';

import '../../fixtures/test_fixtures.dart';
import '../../helpers/sqlite_test_setup.dart';
import '../../mocks/mock_api_client.dart';

/// Tests for [ItemsNotifier] wired against a mock API and an in-memory drift
/// database. Covers the self-load-on-creation behaviour that fixes the stale
/// ApiClient bug (settings change -> new notifier -> automatic reload).
void main() {
  late MockApiClient mockApi;
  late AppDatabase db;

  ProviderContainer makeContainer() {
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(mockApi),
        appDatabaseProvider.overrideWithValue(db),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  /// Give the notifier's async self-load / reloads time to settle.
  Future<void> settle() =>
      Future<void>.delayed(const Duration(milliseconds: 50));

  setUp(() {
    useSystemSqlite();
    mockApi = MockApiClient();
    db = AppDatabase(NativeDatabase.memory());
  });

  tearDown(() async {
    await db.close();
  });

  test('self-loads items when first read, without a manual loadItems call',
      () async {
    mockApi.itemsToReturn = TestItems.sampleList;
    final container = makeContainer();

    // Merely reading the provider creates the notifier, which loads itself.
    container.read(itemsProvider.notifier);
    await settle();

    final state = container.read(itemsProvider);
    expect(mockApi.methodCalls, contains('getItems'));
    expect(state.items.length, TestItems.sampleList.length);
    expect(state.isLoading, false);
    expect(state.error, isNull);
  });

  test('a fresh notifier reloads (mirrors a settings change)', () async {
    mockApi.itemsToReturn = TestItems.sampleList;

    // First container = "app running".
    final c1 = makeContainer();
    c1.read(itemsProvider.notifier);
    await settle();
    expect(c1.read(itemsProvider).items, isNotEmpty);

    // A settings change rebuilds the provider graph -> a brand new notifier.
    // Simulate by creating a second container and confirm it loads on its own.
    final c2 = makeContainer();
    c2.read(itemsProvider.notifier);
    await settle();
    expect(c2.read(itemsProvider).items.length, TestItems.sampleList.length);
    // getItems was called for each fresh notifier.
    expect(
      mockApi.methodCalls.where((m) => m == 'getItems').length,
      greaterThanOrEqualTo(2),
    );
  });

  test('surfaces an error (and stops loading) when the API fails', () async {
    mockApi.setFailure('boom');
    final container = makeContainer();

    container.read(itemsProvider.notifier);
    await settle();

    final state = container.read(itemsProvider);
    expect(state.isLoading, false);
    expect(state.error, isNotNull);
    expect(state.items, isEmpty);
  });

  test('toggleFavorite optimistically flips the flag', () async {
    final item = TestItems.completedItem; // isFavorite == false
    mockApi.itemsToReturn = [item];
    mockApi.singleItemToReturn = item;
    final container = makeContainer();
    final notifier = container.read(itemsProvider.notifier);
    await settle();

    expect(container.read(itemsProvider).items.single.isFavorite, false);

    await notifier.toggleFavorite(item.id);
    await settle();

    expect(mockApi.methodCalls, contains('toggleFavorite'));
    expect(container.read(itemsProvider).items.single.isFavorite, true);
  });

  test('loadItems appends the next page and tracks hasMore', () async {
    final mock = MockApiClient()
      ..itemsByPage = {
        1: [TestItems.completedItem],
        2: [TestItems.favoriteItem],
      }
      ..pagesToReturn = 2;
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(mock),
        appDatabaseProvider.overrideWithValue(db),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(itemsProvider.notifier);
    await settle(); // auto-load page 1

    var state = container.read(itemsProvider);
    expect(state.items.map((i) => i.id), [TestItems.completedItem.id]);
    expect(state.currentPage, 1);
    expect(state.hasMore, true);

    await notifier.loadItems(); // page 2
    await settle();

    state = container.read(itemsProvider);
    expect(
      state.items.map((i) => i.id),
      [TestItems.completedItem.id, TestItems.favoriteItem.id],
    );
    expect(state.currentPage, 2);
    expect(state.hasMore, false);
  });

  test('setSearchQuery reloads with the query applied', () async {
    mockApi.itemsToReturn = TestItems.sampleList;
    final container = makeContainer();
    final notifier = container.read(itemsProvider.notifier);
    await settle();

    await notifier.setSearchQuery('flutter');
    await settle();

    expect(container.read(itemsProvider).searchQuery, 'flutter');
    expect(mockApi.lastCallParams['search'], 'flutter');
  });
}
