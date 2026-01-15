import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import 'package:go_router/go_router.dart';

import '../models/content_item.dart';
import '../providers/items_provider.dart';
import '../providers/share_intent_provider.dart';
import '../providers/topics_provider.dart';
import '../providers/weekly_provider.dart';
import '../widgets/add_note_dialog.dart';
import '../widgets/add_url_dialog.dart';
import '../widgets/item_card.dart';

class InboxScreen extends ConsumerStatefulWidget {
  const InboxScreen({super.key});

  @override
  ConsumerState<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends ConsumerState<InboxScreen> {
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();
  Timer? _debounce;
  bool _isSearching = false;

  @override
  void initState() {
    super.initState();
    // Load initial items
    Future.microtask(() {
      ref.read(itemsProvider.notifier).loadItems(refresh: true);
      // Initialize share intent provider (handles URLs via notifications)
      ref.read(shareIntentProvider);
    });

    // Pagination
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _searchController.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      ref.read(itemsProvider.notifier).setSearchQuery(query);
    });
  }

  void _toggleSearch() {
    setState(() {
      _isSearching = !_isSearching;
      if (!_isSearching) {
        _searchController.clear();
        ref.read(itemsProvider.notifier).setSearchQuery(null);
      }
    });
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      final state = ref.read(itemsProvider);
      if (!state.isLoading && state.hasMore) {
        ref.read(itemsProvider.notifier).loadItems();
      }
    }
  }

  Future<void> _addUrl() async {
    final url = await showDialog<String>(
      context: context,
      builder: (context) => const AddUrlDialog(),
    );

    if (url != null && url.isNotEmpty) {
      final item = await ref.read(itemsProvider.notifier).ingestUrl(url);
      if (mounted) {
        if (item != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Added: ${item.displayTitle}'),
              action: SnackBarAction(
                label: 'View',
                onPressed: () => context.push('/item/${item.id}'),
              ),
            ),
          );
        } else if (ref.read(itemsProvider).hasPendingActions) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('URL queued - will be added when online'),
            ),
          );
        }
      }
    }
  }

  Future<void> _addNote() async {
    final noteData = await showDialog<NoteData>(
      context: context,
      builder: (context) => const AddNoteDialog(),
    );

    if (noteData != null) {
      final item = await ref.read(itemsProvider.notifier).ingestNote(
            noteData.title,
            noteData.text,
          );
      if (mounted) {
        if (item != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Added: ${item.displayTitle}'),
              action: SnackBarAction(
                label: 'View',
                onPressed: () => context.push('/item/${item.id}'),
              ),
            ),
          );
        } else if (ref.read(itemsProvider).hasPendingActions) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Note queued - will be added when online'),
            ),
          );
        }
      }
    }
  }

  Future<void> _generateWeeklySummary() async {
    final weeklyState = ref.read(weeklyProvider);
    if (weeklyState.isGenerating) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Summary wird bereits generiert...')),
      );
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Wochenzusammenfassung wird generiert...'),
        duration: Duration(seconds: 2),
      ),
    );

    await ref.read(weeklyProvider.notifier).generateCurrentWeekSummary();

    if (mounted) {
      final newState = ref.read(weeklyProvider);
      if (newState.error != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Fehler: ${newState.error}'),
            backgroundColor: Colors.red,
          ),
        );
      }
      // Notification is shown automatically by the provider
    }
  }

  void _showAddOptions() {
    final weeklyState = ref.read(weeklyProvider);

    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.link),
              title: const Text('Add URL'),
              subtitle: const Text('Save a link from the web'),
              onTap: () {
                Navigator.pop(context);
                _addUrl();
              },
            ),
            ListTile(
              leading: const Icon(Icons.note_add),
              title: const Text('Add Note'),
              subtitle: const Text('Write a quick note'),
              onTap: () {
                Navigator.pop(context);
                _addNote();
              },
            ),
            const Divider(),
            ListTile(
              leading: Icon(
                Icons.auto_awesome,
                color: weeklyState.isGenerating ? Colors.grey : null,
              ),
              title: const Text('Wochenzusammenfassung'),
              subtitle: Text(
                weeklyState.isGenerating
                    ? 'Wird generiert...'
                    : 'KI-Summary erstellen (Benachrichtigung wenn fertig)',
              ),
              enabled: !weeklyState.isGenerating,
              onTap: () {
                Navigator.pop(context);
                _generateWeeklySummary();
              },
            ),
          ],
        ),
      ),
    );
  }

  AppBar _buildNormalAppBar() {
    return AppBar(
      title: _isSearching
          ? TextField(
              controller: _searchController,
              autofocus: true,
              decoration: const InputDecoration(
                hintText: 'Search...',
                border: InputBorder.none,
              ),
              onChanged: _onSearchChanged,
            )
          : const Text('Inbox'),
      actions: [
        IconButton(
          icon: Icon(_isSearching ? Icons.close : Icons.search),
          onPressed: _toggleSearch,
        ),
        _buildSortButton(),
        IconButton(
          icon: const Icon(Icons.hub),
          tooltip: 'Knowledge Graph',
          onPressed: () => context.push('/graph'),
        ),
        IconButton(
          icon: const Icon(Icons.auto_awesome),
          tooltip: 'Weekly Summary',
          onPressed: () => context.push('/weekly'),
        ),
      ],
    );
  }

  AppBar _buildSelectionAppBar(ItemsState state) {
    return AppBar(
      leading: IconButton(
        icon: const Icon(Icons.close),
        onPressed: () => ref.read(itemsProvider.notifier).exitSelectionMode(),
      ),
      title: Text('${state.selectedCount} selected'),
      actions: [
        IconButton(
          icon: const Icon(Icons.select_all),
          tooltip: 'Select All',
          onPressed: () => ref.read(itemsProvider.notifier).selectAll(),
        ),
        IconButton(
          icon: const Icon(Icons.mark_email_read),
          tooltip: 'Mark as Read',
          onPressed: state.selectedCount > 0
              ? () => _bulkMarkRead()
              : null,
        ),
        if (!state.archivedOnly)
          IconButton(
            icon: const Icon(Icons.archive_outlined),
            tooltip: 'Archive',
            onPressed: state.selectedCount > 0
                ? () => _bulkArchive()
                : null,
          ),
        IconButton(
          icon: const Icon(Icons.delete_outline),
          tooltip: 'Delete',
          onPressed: state.selectedCount > 0
              ? () => _showBulkDeleteConfirmation()
              : null,
        ),
      ],
    );
  }

  Future<void> _bulkMarkRead() async {
    await ref.read(itemsProvider.notifier).bulkMarkRead();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Items marked as read')),
      );
    }
  }

  Future<void> _bulkArchive() async {
    final count = ref.read(itemsProvider).selectedCount;
    await ref.read(itemsProvider.notifier).bulkArchive();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$count item${count > 1 ? 's' : ''} archived')),
      );
    }
  }

  Future<void> _showBulkDeleteConfirmation() async {
    final state = ref.read(itemsProvider);
    final count = state.selectedCount;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Items'),
        content: Text('Are you sure you want to delete $count item${count > 1 ? 's' : ''}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: FilledButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await ref.read(itemsProvider.notifier).bulkDelete();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$count item${count > 1 ? 's' : ''} deleted')),
        );
      }
    }
  }

  Widget _buildSortButton() {
    final state = ref.watch(itemsProvider);
    return PopupMenuButton<SortField>(
      icon: const Icon(Icons.sort),
      tooltip: 'Sort',
      onSelected: (field) {
        // If selecting the same field, toggle order; otherwise, use desc
        if (field == state.sortBy) {
          ref.read(itemsProvider.notifier).toggleSortOrder();
        } else {
          ref.read(itemsProvider.notifier).setSort(field, SortOrder.desc);
        }
      },
      itemBuilder: (context) => SortField.values.map((field) {
        final isSelected = field == state.sortBy;
        return PopupMenuItem<SortField>(
          value: field,
          child: Row(
            children: [
              if (isSelected)
                Icon(
                  state.sortOrder == SortOrder.desc
                      ? Icons.arrow_downward
                      : Icons.arrow_upward,
                  size: 18,
                  color: Theme.of(context).colorScheme.primary,
                )
              else
                const SizedBox(width: 18),
              const SizedBox(width: 8),
              Text(
                field.displayName,
                style: isSelected
                    ? TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).colorScheme.primary,
                      )
                    : null,
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(itemsProvider);
    final topicsAsync = ref.watch(topicsProvider);

    return Scaffold(
      appBar: state.isSelectionMode
          ? _buildSelectionAppBar(state)
          : _buildNormalAppBar(),
      body: Column(
        children: [
          // Offline indicator banner
          if (state.isOffline || state.isFromCache)
            _buildOfflineBanner(state),
          // Filter chips (hide in selection mode)
          if (!state.isSelectionMode)
            topicsAsync.when(
              data: (topics) => _buildTopicChips(topics, state.selectedTopicId),
              loading: () => _buildTopicChips([], state.selectedTopicId),
              error: (e, s) => _buildTopicChips([], state.selectedTopicId),
            ),
          // Items list
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.read(itemsProvider.notifier).refresh(),
              child: _buildContent(state),
            ),
          ),
        ],
      ),
      floatingActionButton: state.isSelectionMode
          ? null
          : FloatingActionButton.extended(
              onPressed: _showAddOptions,
              icon: const Icon(Icons.add),
              label: const Text('Add'),
            ),
    );
  }

  Widget _buildOfflineBanner(ItemsState state) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: state.hasPendingActions
          ? Colors.orange.shade100
          : Colors.grey.shade200,
      child: Row(
        children: [
          Icon(
            state.hasPendingActions
                ? Icons.sync_problem
                : Icons.cloud_off,
            size: 18,
            color: state.hasPendingActions
                ? Colors.orange.shade800
                : Colors.grey.shade700,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              state.hasPendingActions
                  ? 'Offline - ${_pendingActionsText(state)}'
                  : 'Offline - showing cached data',
              style: TextStyle(
                fontSize: 13,
                color: state.hasPendingActions
                    ? Colors.orange.shade800
                    : Colors.grey.shade700,
              ),
            ),
          ),
          TextButton(
            onPressed: () => ref.read(itemsProvider.notifier).refresh(),
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  String _pendingActionsText(ItemsState state) {
    return 'changes will sync when online';
  }

  Widget _buildTopicChips(List<Topic> topics, int? selectedTopicId) {
    final state = ref.watch(itemsProvider);

    return SizedBox(
      height: 50,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        children: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: const Text('All'),
              selected: selectedTopicId == null && !state.favoritesOnly && !state.unreadOnly && !state.archivedOnly,
              onSelected: (_) {
                ref.read(itemsProvider.notifier).setTopicFilter(null);
                ref.read(itemsProvider.notifier).setFavoritesFilter(false);
                ref.read(itemsProvider.notifier).setUnreadFilter(false);
                ref.read(itemsProvider.notifier).setArchivedFilter(false);
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              avatar: Icon(
                state.favoritesOnly ? Icons.star : Icons.star_border,
                size: 18,
                color: state.favoritesOnly ? Colors.amber : null,
              ),
              label: const Text('Favorites'),
              selected: state.favoritesOnly,
              onSelected: (selected) {
                ref.read(itemsProvider.notifier).setFavoritesFilter(selected);
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              avatar: Icon(
                state.unreadOnly ? Icons.mark_email_unread : Icons.mark_email_read,
                size: 18,
                color: state.unreadOnly ? Theme.of(context).colorScheme.primary : null,
              ),
              label: const Text('Unread'),
              selected: state.unreadOnly,
              onSelected: (selected) {
                ref.read(itemsProvider.notifier).setUnreadFilter(selected);
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              avatar: Icon(
                state.archivedOnly ? Icons.archive : Icons.archive_outlined,
                size: 18,
                color: state.archivedOnly ? Theme.of(context).colorScheme.primary : null,
              ),
              label: const Text('Archived'),
              selected: state.archivedOnly,
              onSelected: (selected) {
                ref.read(itemsProvider.notifier).setArchivedFilter(selected);
              },
            ),
          ),
          ...topics.map((topic) => Padding(
                padding: const EdgeInsets.only(right: 8),
                child: FilterChip(
                  label: Text(topic.name),
                  selected: selectedTopicId == topic.id,
                  onSelected: (_) {
                    ref.read(itemsProvider.notifier).setTopicFilter(
                          selectedTopicId == topic.id ? null : topic.id,
                        );
                  },
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildContent(ItemsState state) {
    if (state.isLoading && state.items.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.error != null && state.items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text('Error: ${state.error}'),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () =>
                  ref.read(itemsProvider.notifier).loadItems(refresh: true),
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (state.items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.inbox_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 16),
            Text(
              'No items yet',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Add your first URL to get started',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.only(bottom: 80),
      itemCount: state.items.length + (state.hasMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index >= state.items.length) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: CircularProgressIndicator(),
            ),
          );
        }

        final item = state.items[index];
        final itemCard = ItemCard(
          item: item,
          onTap: () => context.push('/item/${item.id}'),
          onToggleFavorite: () =>
              ref.read(itemsProvider.notifier).toggleFavorite(item.id),
          onToggleRead: () =>
              ref.read(itemsProvider.notifier).toggleRead(item.id),
          onLongPress: () {
            if (!state.isSelectionMode) {
              ref.read(itemsProvider.notifier).enterSelectionMode();
              ref.read(itemsProvider.notifier).toggleSelection(item.id);
            }
          },
          isSelectionMode: state.isSelectionMode,
          isSelected: state.isSelected(item.id),
          onToggleSelection: () =>
              ref.read(itemsProvider.notifier).toggleSelection(item.id),
        );

        // Disable swipe actions in selection mode
        if (state.isSelectionMode) {
          return itemCard;
        }

        return Slidable(
          key: ValueKey(item.id),
          endActionPane: ActionPane(
            motion: const ScrollMotion(),
            children: [
              SlidableAction(
                onPressed: (_) {
                  ref.read(itemsProvider.notifier).toggleArchive(item.id);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(item.isArchived ? 'Item unarchived' : 'Item archived'),
                    ),
                  );
                },
                backgroundColor: item.isArchived ? Colors.green : Colors.orange,
                foregroundColor: Colors.white,
                icon: item.isArchived ? Icons.unarchive : Icons.archive,
                label: item.isArchived ? 'Unarchive' : 'Archive',
              ),
              SlidableAction(
                onPressed: (_) {
                  ref.read(itemsProvider.notifier).deleteItem(item.id);
                },
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
                icon: Icons.delete,
                label: 'Delete',
              ),
            ],
          ),
          child: itemCard,
        );
      },
    );
  }
}
