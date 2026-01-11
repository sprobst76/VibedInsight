import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/content_item.dart';
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
    );
  }

  bool get hasFilters => searchQuery != null || selectedTopicId != null || favoritesOnly || unreadOnly || archivedOnly;

  int get selectedCount => selectedIds.length;

  bool isSelected(int id) => selectedIds.contains(id);
}

class ItemsNotifier extends StateNotifier<ItemsState> {
  final ApiClient _apiClient;

  ItemsNotifier(this._apiClient) : super(ItemsState());

  Future<void> loadItems({bool refresh = false}) async {
    if (state.isLoading) return;

    final page = refresh ? 1 : state.currentPage + 1;

    state = state.copyWith(
      isLoading: true,
      error: null,
      items: refresh ? [] : state.items,
    );

    try {
      final result = await _apiClient.getItems(
        page: page,
        topicId: state.selectedTopicId,
        search: state.searchQuery,
        favoritesOnly: state.favoritesOnly,
        unreadOnly: state.unreadOnly,
        archivedOnly: state.archivedOnly,
        sortBy: state.sortBy,
        sortOrder: state.sortOrder,
      );

      state = state.copyWith(
        items: refresh ? result.items : [...state.items, ...result.items],
        isLoading: false,
        hasMore: page < result.pages,
        currentPage: page,
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
    try {
      final updated = await _apiClient.toggleFavorite(id);

      // Update the item in the list
      state = state.copyWith(
        items: state.items.map((item) {
          return item.id == id ? updated : item;
        }).toList(),
      );

      // If we're filtering by favorites and the item is now unfavorited, remove it
      if (state.favoritesOnly && !updated.isFavorite) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> toggleRead(int id) async {
    try {
      final updated = await _apiClient.toggleRead(id);

      // Update the item in the list
      state = state.copyWith(
        items: state.items.map((item) {
          return item.id == id ? updated : item;
        }).toList(),
      );

      // If we're filtering by unread and the item is now read, remove it
      if (state.unreadOnly && updated.isRead) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> toggleArchive(int id) async {
    try {
      final updated = await _apiClient.toggleArchive(id);

      // Update the item in the list
      state = state.copyWith(
        items: state.items.map((item) {
          return item.id == id ? updated : item;
        }).toList(),
      );

      // If not viewing archived and item is now archived, remove it from view
      if (!state.archivedOnly && updated.isArchived) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
      // If viewing archived only and item is now unarchived, remove it from view
      if (state.archivedOnly && !updated.isArchived) {
        state = state.copyWith(
          items: state.items.where((item) => item.id != id).toList(),
        );
      }
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<ContentItem?> ingestUrl(String url) async {
    try {
      final item = await _apiClient.ingestUrl(url);
      state = state.copyWith(
        items: [item, ...state.items],
      );
      return item;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return null;
    }
  }

  Future<ContentItem?> ingestNote(String title, String text) async {
    try {
      final item = await _apiClient.ingestText(title: title, text: text);
      state = state.copyWith(
        items: [item, ...state.items],
      );
      return item;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return null;
    }
  }

  Future<void> deleteItem(int id) async {
    try {
      await _apiClient.deleteItem(id);
      state = state.copyWith(
        items: state.items.where((item) => item.id != id).toList(),
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
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
  final apiClient = ref.watch(apiClientProvider);
  return ItemsNotifier(apiClient);
});

// Single item provider (with relations)
final itemDetailProvider =
    FutureProvider.family<ContentItemWithRelations, int>((ref, id) async {
  final apiClient = ref.watch(apiClientProvider);
  return apiClient.getItemWithRelations(id);
});
