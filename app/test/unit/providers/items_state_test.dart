import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/models/content_item.dart';
import 'package:vibedinsight/providers/items_provider.dart';

import '../../fixtures/test_fixtures.dart';

void main() {
  group('ItemsState', () {
    test('initial state has correct defaults', () {
      final state = ItemsState();

      expect(state.items, isEmpty);
      expect(state.isLoading, false);
      expect(state.hasMore, true);
      expect(state.currentPage, 0);
      expect(state.error, isNull);
      expect(state.searchQuery, isNull);
      expect(state.selectedTopicId, isNull);
      expect(state.favoritesOnly, false);
      expect(state.unreadOnly, false);
      expect(state.archivedOnly, false);
      expect(state.sortBy, SortField.date);
      expect(state.sortOrder, SortOrder.desc);
      expect(state.isSelectionMode, false);
      expect(state.selectedIds, isEmpty);
      expect(state.isOffline, false);
      expect(state.isFromCache, false);
      expect(state.hasPendingActions, false);
    });

    test('copyWith preserves unmodified values', () {
      final original = ItemsState(
        items: TestItems.sampleList,
        isLoading: true,
        currentPage: 2,
        searchQuery: 'test',
        favoritesOnly: true,
      );

      final copied = original.copyWith(isLoading: false);

      expect(copied.items, original.items);
      expect(copied.isLoading, false);
      expect(copied.currentPage, 2);
      expect(copied.searchQuery, 'test');
      expect(copied.favoritesOnly, true);
    });

    test('copyWith with clearSearch removes searchQuery', () {
      final state = ItemsState(searchQuery: 'test');
      final cleared = state.copyWith(clearSearch: true);

      expect(cleared.searchQuery, isNull);
    });

    test('copyWith with clearTopic removes selectedTopicId', () {
      final state = ItemsState(selectedTopicId: 1);
      final cleared = state.copyWith(clearTopic: true);

      expect(cleared.selectedTopicId, isNull);
    });

    test('copyWith can update multiple values at once', () {
      final state = ItemsState();
      final updated = state.copyWith(
        isLoading: true,
        currentPage: 5,
        hasMore: false,
        error: 'Test error',
      );

      expect(updated.isLoading, true);
      expect(updated.currentPage, 5);
      expect(updated.hasMore, false);
      expect(updated.error, 'Test error');
    });

    group('hasFilters', () {
      test('returns false when no filters active', () {
        expect(ItemsState().hasFilters, false);
      });

      test('returns true when searchQuery is set', () {
        expect(ItemsState(searchQuery: 'test').hasFilters, true);
      });

      test('returns true when selectedTopicId is set', () {
        expect(ItemsState(selectedTopicId: 1).hasFilters, true);
      });

      test('returns true when favoritesOnly is true', () {
        expect(ItemsState(favoritesOnly: true).hasFilters, true);
      });

      test('returns true when unreadOnly is true', () {
        expect(ItemsState(unreadOnly: true).hasFilters, true);
      });

      test('returns true when archivedOnly is true', () {
        expect(ItemsState(archivedOnly: true).hasFilters, true);
      });

      test('returns true when multiple filters are active', () {
        final state = ItemsState(
          searchQuery: 'test',
          selectedTopicId: 1,
          favoritesOnly: true,
        );
        expect(state.hasFilters, true);
      });
    });

    group('selection', () {
      test('selectedCount returns correct count', () {
        final state = ItemsState(selectedIds: {1, 2, 3});
        expect(state.selectedCount, 3);
      });

      test('selectedCount returns 0 for empty selection', () {
        expect(ItemsState().selectedCount, 0);
      });

      test('isSelected returns true for selected ids', () {
        final state = ItemsState(selectedIds: {1, 2});
        expect(state.isSelected(1), true);
        expect(state.isSelected(2), true);
      });

      test('isSelected returns false for non-selected ids', () {
        final state = ItemsState(selectedIds: {1, 2});
        expect(state.isSelected(3), false);
        expect(state.isSelected(0), false);
      });

      test('copyWith can update selectedIds', () {
        final state = ItemsState(selectedIds: {1, 2});
        final updated = state.copyWith(selectedIds: {3, 4, 5});

        expect(updated.selectedIds, {3, 4, 5});
        expect(updated.selectedCount, 3);
      });
    });

    group('offline state', () {
      test('isOffline can be set via copyWith', () {
        final state = ItemsState();
        final offline = state.copyWith(isOffline: true);

        expect(offline.isOffline, true);
      });

      test('isFromCache can be set via copyWith', () {
        final state = ItemsState();
        final fromCache = state.copyWith(isFromCache: true);

        expect(fromCache.isFromCache, true);
      });

      test('hasPendingActions can be set via copyWith', () {
        final state = ItemsState();
        final pending = state.copyWith(hasPendingActions: true);

        expect(pending.hasPendingActions, true);
      });
    });

    group('sorting', () {
      test('default sort is date descending', () {
        final state = ItemsState();
        expect(state.sortBy, SortField.date);
        expect(state.sortOrder, SortOrder.desc);
      });

      test('copyWith can update sortBy', () {
        final state = ItemsState();
        final updated = state.copyWith(sortBy: SortField.title);

        expect(updated.sortBy, SortField.title);
        expect(updated.sortOrder, SortOrder.desc);
      });

      test('copyWith can update sortOrder', () {
        final state = ItemsState();
        final updated = state.copyWith(sortOrder: SortOrder.asc);

        expect(updated.sortBy, SortField.date);
        expect(updated.sortOrder, SortOrder.asc);
      });

      test('copyWith can update both sort fields', () {
        final state = ItemsState();
        final updated = state.copyWith(
          sortBy: SortField.title,
          sortOrder: SortOrder.asc,
        );

        expect(updated.sortBy, SortField.title);
        expect(updated.sortOrder, SortOrder.asc);
      });
    });

    group('items list manipulation', () {
      test('copyWith can replace items list', () {
        final state = ItemsState(items: [TestItems.completedItem]);
        final updated = state.copyWith(items: TestItems.sampleList);

        expect(updated.items.length, TestItems.sampleList.length);
      });

      test('copyWith with empty items list clears items', () {
        final state = ItemsState(items: TestItems.sampleList);
        final cleared = state.copyWith(items: []);

        expect(cleared.items, isEmpty);
      });
    });

    group('error handling', () {
      test('error can be set via copyWith', () {
        final state = ItemsState();
        final withError = state.copyWith(error: 'Network error');

        expect(withError.error, 'Network error');
      });

      test('error is cleared when set to null in copyWith', () {
        final state = ItemsState(error: 'Old error');
        // Error parameter behavior: it always replaces (even with null)
        final cleared = state.copyWith(error: null);

        expect(cleared.error, isNull);
      });
    });
  });
}
