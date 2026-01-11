import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/content_item.dart';
import '../repositories/items_repository.dart';
import 'api_provider.dart';

// Items list state
class ItemsState {
  final List<ContentItem> items;
  final bool isLoading;
  final bool hasMore;
  final int currentPage;
  final String? error;
  final String? searchQuery;
  final int? selectedTopicId;
  final bool favoritesOnly;
  final bool unreadOnly;
  final bool archivedOnly;
  final SortField sortBy;
  final SortOrder sortOrder;
  final bool isSelectionMode;
  final Set<int> selectedIds;
  final bool isOffline;
  final bool isFromCache;
  final bool hasPendingActions;

  ItemsState({
    this.items = const [],
    this.isLoading = false,
    this.hasMore = true,
    this.currentPage = 0,
    this.error,
    this.searchQuery,
    this.selectedTopicId,
    this.favoritesOnly = false,
    this.unreadOnly = false,
    this.archivedOnly = false,
    this.sortBy = SortField.date,
    this.sortOrder = SortOrder.desc,
    this.isSelectionMode = false,
    this.selectedIds = const {},
    this.isOffline = false,
    this.isFromCache = false,
    this.hasPendingActions = false,
  });

  ItemsState copyWith({
    List<ContentItem>? items,
    bool? isLoading,
    bool? hasMore,
    int? currentPage,
    String? error,
    String? searchQuery,
    int? selectedTopicId,
    bool? favoritesOnly,
    bool? unreadOnly,
    bool? archivedOnly,
    SortField? sortBy,
    SortOrder? sortOrder,
    bool? isSelectionMode,
    Set<int>? selectedIds,
    bool? isOffline,
    bool? isFromCache,
    bool? hasPendingActions,
    bool clearSearch = false,
    bool clearTopic = false,
  }) {
    return ItemsState(
      items: items ?? this.items,
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
      currentPage: currentPage ?? this.currentPage,
      error: error,
      searchQuery: clearSearch ? null : (searchQuery ?? this.searchQuery),
      selectedTopicId: clearTopic ? null : (selectedTopicId ?? this.selectedTopicId),
      favoritesOnly: favoritesOnly ?? this.favoritesOnly,
      unreadOnly: unreadOnly ?? this.unreadOnly,
      archivedOnly: archivedOnly ?? this.archivedOnly,
      sortBy: sortBy ?? this.sortBy,
      sortOrder: sortOrder ?? this.sortOrder,
      isSelectionMode: isSelectionMode ?? this.isSelectionMode,
      selectedIds: selectedIds ?? this.selectedIds,
      isOffline: isOffline ?? this.isOffline,
      isFromCache: isFromCache ?? this.isFromCache,
      hasPendingActions: hasPendingActions ?? this.hasPendingActions,
    );
  }

  bool get hasFilters => searchQuery != null || selectedTopicId != null || favoritesOnly || unreadOnly || archivedOnly;

  int get selectedCount => selectedIds.length;

  bool isSelected(int id) => selectedIds.contains(id);
}

class ItemsNotifier extends StateNotifier<ItemsState> {
  final ItemsRepository _repository;
  final ApiClient _apiClient;

  ItemsNotifier(this._repository, this._apiClient) : super(ItemsState()) {
    // Listen to online status changes
    _repository.onlineStatus.listen((isOnline) {
      state = state.copyWith(isOffline: !isOnline);
      if (isOnline) {
        // Sync pending actions when back online
        _syncPendingActions();
      }
    });
  }

  Future<void> _syncPendingActions() async {
    final result = await _repository.syncPendingActions();
    if (result.synced > 0) {
      // Refresh to get latest data after sync
      await loadItems(refresh: true);
    }
    final hasPending = await _repository.hasPendingActions();
    state = state.copyWith(hasPendingActions: hasPending);
  }

  Future<void> loadItems({bool refresh = false}) async {
    if (state.isLoading) return;

    final page = refresh ? 1 : state.currentPage + 1;

    state = state.copyWith(
      isLoading: true,
      error: null,
      items: refresh ? [] : state.items,
    );

    try {
      final result = await _repository.getItems(
        page: page,
        topicId: state.selectedTopicId,
        search: state.searchQuery,
        favoritesOnly: state.favoritesOnly,
        unreadOnly: state.unreadOnly,
        archivedOnly: state.archivedOnly,
        sortBy: state.sortBy,
        sortOrder: state.sortOrder,
      );

      final hasPending = await _repository.hasPendingActions();

      state = state.copyWith(
        items: refresh ? result.items : [...state.items, ...result.items],
        isLoading: false,
        hasMore: page < result.pages,
        currentPage: page,
        isFromCache: result.isFromCache,
        isOffline: result.isFromCache,
        hasPendingActions: hasPending,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
    }
  }

  Future<void> refresh() async {
    await loadItems(refresh: true);
  }

  Future<void> setSearchQuery(String? query) async {
    final trimmedQuery = query?.trim();
    final newQuery = (trimmedQuery?.isEmpty ?? true) ? null : trimmedQuery;

    if (newQuery == state.searchQuery) return;

    state = state.copyWith(
      searchQuery: newQuery,
      clearSearch: newQuery == null,
    );
    await loadItems(refresh: true);
  }

  Future<void> setTopicFilter(int? topicId) async {
    if (topicId == state.selectedTopicId) return;

    state = state.copyWith(
      selectedTopicId: topicId,
      clearTopic: topicId == null,
    );
    await loadItems(refresh: true);
  }

  void clearFilters() {
    state = state.copyWith(
      clearSearch: true,
      clearTopic: true,
    );
    loadItems(refresh: true);
  }

  Future<void> setSort(SortField sortBy, SortOrder sortOrder) async {
    if (sortBy == state.sortBy && sortOrder == state.sortOrder) return;

    state = state.copyWith(
      sortBy: sortBy,
      sortOrder: sortOrder,
    );
    await loadItems(refresh: true);
  }

  void toggleSortOrder() {
    final newOrder = state.sortOrder == SortOrder.desc
        ? SortOrder.asc
        : SortOrder.desc;
    setSort(state.sortBy, newOrder);
  }

  Future<void> setFavoritesFilter(bool favoritesOnly) async {
    if (favoritesOnly == state.favoritesOnly) return;

    state = state.copyWith(favoritesOnly: favoritesOnly);
    await loadItems(refresh: true);
  }

  Future<void> setUnreadFilter(bool unreadOnly) async {
    if (unreadOnly == state.unreadOnly) return;

    state = state.copyWith(unreadOnly: unreadOnly);
    await loadItems(refresh: true);
  }

  Future<void> setArchivedFilter(bool archivedOnly) async {
    if (archivedOnly == state.archivedOnly) return;

    state = state.copyWith(archivedOnly: archivedOnly);
    await loadItems(refresh: true);
  }

  Future<void> toggleFavorite(int id) async {
    final currentItem = state.items.firstWhere((item) => item.id == id);
    final currentValue = currentItem.isFavorite;

    // Optimistic update
    state = state.copyWith(
      items: state.items.map((item) {
        return item.id == id ? item.copyWith(isFavorite: !currentValue) : item;
      }).toList(),
    );

    try {
      await _repository.toggleFavorite(id, currentValue);
      final hasPending = await _repository.hasPendingActions();
      state = state.copyWith(hasPendingActions: hasPending);

      // If we're filtering by favorites and the item is now unfavorited, remove it
      if (state.favoritesOnly && currentValue) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
    } catch (e) {
      // Revert on error
      state = state.copyWith(
        items: state.items.map((item) {
          return item.id == id ? item.copyWith(isFavorite: currentValue) : item;
        }).toList(),
        error: e.toString(),
      );
    }
  }

  Future<void> toggleRead(int id) async {
    final currentItem = state.items.firstWhere((item) => item.id == id);
    final currentValue = currentItem.isRead;

    // Optimistic update
    state = state.copyWith(
      items: state.items.map((item) {
        return item.id == id ? item.copyWith(isRead: !currentValue) : item;
      }).toList(),
    );

    try {
      await _repository.toggleRead(id, currentValue);
      final hasPending = await _repository.hasPendingActions();
      state = state.copyWith(hasPendingActions: hasPending);

      // If we're filtering by unread and the item is now read, remove it
      if (state.unreadOnly && !currentValue) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
    } catch (e) {
      // Revert on error
      state = state.copyWith(
        items: state.items.map((item) {
          return item.id == id ? item.copyWith(isRead: currentValue) : item;
        }).toList(),
        error: e.toString(),
      );
    }
  }

  Future<void> toggleArchive(int id) async {
    final currentItem = state.items.firstWhere((item) => item.id == id);
    final currentValue = currentItem.isArchived;

    // Optimistic update
    state = state.copyWith(
      items: state.items.map((item) {
        return item.id == id ? item.copyWith(isArchived: !currentValue) : item;
      }).toList(),
    );

    try {
      await _repository.toggleArchive(id, currentValue);
      final hasPending = await _repository.hasPendingActions();
      state = state.copyWith(hasPendingActions: hasPending);

      // If not viewing archived and item is now archived, remove it from view
      if (!state.archivedOnly && !currentValue) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
      // If viewing archived only and item is now unarchived, remove it from view
      if (state.archivedOnly && currentValue) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
    } catch (e) {
      // Revert on error
      state = state.copyWith(
        items: state.items.map((item) {
          return item.id == id ? item.copyWith(isArchived: currentValue) : item;
        }).toList(),
        error: e.toString(),
      );
    }
  }

  Future<ContentItem?> ingestUrl(String url) async {
    try {
      final result = await _repository.ingestUrl(url);
      final hasPending = await _repository.hasPendingActions();

      if (result.item != null) {
        state = state.copyWith(
          items: [result.item!, ...state.items],
          hasPendingActions: hasPending,
        );
        return result.item;
      } else if (result.isPending) {
        // Queued for later sync
        state = state.copyWith(hasPendingActions: true);
        return null;
      }
      return null;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return null;
    }
  }

  Future<ContentItem?> ingestNote(String title, String text) async {
    try {
      final result = await _repository.ingestNote(title: title, text: text);
      final hasPending = await _repository.hasPendingActions();

      if (result.item != null) {
        state = state.copyWith(
          items: [result.item!, ...state.items],
          hasPendingActions: hasPending,
        );
        return result.item;
      } else if (result.isPending) {
        // Queued for later sync
        state = state.copyWith(hasPendingActions: true);
        return null;
      }
      return null;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return null;
    }
  }

  Future<void> deleteItem(int id) async {
    // Optimistic removal
    final removedItem = state.items.firstWhere((item) => item.id == id);
    state = state.copyWith(
      items: state.items.where((item) => item.id != id).toList(),
    );

    try {
      await _repository.deleteItem(id);
      final hasPending = await _repository.hasPendingActions();
      state = state.copyWith(hasPendingActions: hasPending);
    } catch (e) {
      // Revert on error
      state = state.copyWith(
        items: [removedItem, ...state.items],
        error: e.toString(),
      );
    }
  }

  void updateItem(ContentItem updatedItem) {
    state = state.copyWith(
      items: state.items.map((item) {
        return item.id == updatedItem.id ? updatedItem : item;
      }).toList(),
    );
  }

  // Selection Mode
  void enterSelectionMode() {
    state = state.copyWith(
      isSelectionMode: true,
      selectedIds: {},
    );
  }

  void exitSelectionMode() {
    state = state.copyWith(
      isSelectionMode: false,
      selectedIds: {},
    );
  }

  void toggleSelection(int id) {
    final newSelectedIds = Set<int>.from(state.selectedIds);
    if (newSelectedIds.contains(id)) {
      newSelectedIds.remove(id);
    } else {
      newSelectedIds.add(id);
    }

    // Auto-exit selection mode if no items selected
    if (newSelectedIds.isEmpty) {
      state = state.copyWith(
        isSelectionMode: false,
        selectedIds: {},
      );
    } else {
      state = state.copyWith(selectedIds: newSelectedIds);
    }
  }

  void selectAll() {
    state = state.copyWith(
      selectedIds: state.items.map((item) => item.id).toSet(),
    );
  }

  void clearSelection() {
    state = state.copyWith(selectedIds: {});
  }

  // Bulk Operations
  Future<void> bulkDelete() async {
    if (state.selectedIds.isEmpty) return;

    try {
      final ids = state.selectedIds.toList();
      final deletedIds = await _apiClient.bulkDeleteItems(ids);

      state = state.copyWith(
        items: state.items.where((item) => !deletedIds.contains(item.id)).toList(),
        isSelectionMode: false,
        selectedIds: {},
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> bulkMarkRead() async {
    if (state.selectedIds.isEmpty) return;

    try {
      final ids = state.selectedIds.toList();
      final updatedItems = await _apiClient.bulkMarkRead(ids);

      // Update items in the list
      final updatedMap = {for (var item in updatedItems) item.id: item};
      var newItems = state.items.map((item) {
        return updatedMap[item.id] ?? item;
      }).toList();

      // If filtering by unread, remove the now-read items
      if (state.unreadOnly) {
        newItems = newItems.where((item) => !item.isRead).toList();
      }

      state = state.copyWith(
        items: newItems,
        isSelectionMode: false,
        selectedIds: {},
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> bulkArchive() async {
    if (state.selectedIds.isEmpty) return;

    try {
      final ids = state.selectedIds.toList();
      await _apiClient.bulkArchive(ids);

      // Remove archived items from the list (since we're not viewing archived)
      state = state.copyWith(
        items: state.items.where((item) => !ids.contains(item.id)).toList(),
        isSelectionMode: false,
        selectedIds: {},
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }
}

final itemsProvider = StateNotifierProvider<ItemsNotifier, ItemsState>((ref) {
  final repository = ref.watch(itemsRepositoryProvider);
  final apiClient = ref.watch(apiClientProvider);
  return ItemsNotifier(repository, apiClient);
});

// Single item provider (with relations)
final itemDetailProvider =
    FutureProvider.family<ContentItemWithRelations, int>((ref, id) async {
  final apiClient = ref.watch(apiClientProvider);
  return apiClient.getItemWithRelations(id);
});
