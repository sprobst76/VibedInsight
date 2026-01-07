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

  ItemsState({
    this.items = const [],
    this.isLoading = false,
    this.hasMore = true,
    this.currentPage = 0,
    this.error,
    this.searchQuery,
    this.selectedTopicId,
  });

  ItemsState copyWith({
    List<ContentItem>? items,
    bool? isLoading,
    bool? hasMore,
    int? currentPage,
    String? error,
    String? searchQuery,
    int? selectedTopicId,
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
    );
  }

  bool get hasFilters => searchQuery != null || selectedTopicId != null;
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
}

final itemsProvider = StateNotifierProvider<ItemsNotifier, ItemsState>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return ItemsNotifier(apiClient);
});

// Single item provider
final itemDetailProvider =
    FutureProvider.family<ContentItem, int>((ref, id) async {
  final apiClient = ref.watch(apiClientProvider);
  return apiClient.getItem(id);
});
