import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import 'package:go_router/go_router.dart';

import '../models/content_item.dart';
import '../providers/items_provider.dart';
import '../providers/share_intent_provider.dart';
import '../providers/topics_provider.dart';
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
      // Check for initial shared content
      _handleSharedContent();
    });

    // Pagination
    _scrollController.addListener(_onScroll);
  }

  void _handleSharedContent() {
    final sharedContent = ref.read(shareIntentProvider);
    if (sharedContent != null && sharedContent.hasUrl) {
      _showShareConfirmDialog(sharedContent.extractUrl()!);
      ref.read(shareIntentProvider.notifier).clear();
    }
  }

  Future<void> _showShareConfirmDialog(String url) async {
    final shouldAdd = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add shared URL?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Do you want to add this URL to your knowledge base?'),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                url,
                style: Theme.of(context).textTheme.bodySmall,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Add'),
          ),
        ],
      ),
    );

    if (shouldAdd == true && mounted) {
      await _ingestSharedUrl(url);
    }
  }

  Future<void> _ingestSharedUrl(String url) async {
    // Show loading indicator
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Row(
          children: [
            SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            SizedBox(width: 16),
            Text('Adding URL...'),
          ],
        ),
        duration: Duration(seconds: 30),
      ),
    );

    final item = await ref.read(itemsProvider.notifier).ingestUrl(url);

    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();

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
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Failed to add URL'),
          backgroundColor: Colors.red,
        ),
      );
    }
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
      if (item != null && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Added: ${item.displayTitle}'),
            action: SnackBarAction(
              label: 'View',
              onPressed: () => context.push('/item/${item.id}'),
            ),
          ),
        );
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
      if (item != null && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Added: ${item.displayTitle}'),
            action: SnackBarAction(
              label: 'View',
              onPressed: () => context.push('/item/${item.id}'),
            ),
          ),
        );
      }
    }
  }

  void _showAddOptions() {
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
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(itemsProvider);
    final topicsAsync = ref.watch(topicsProvider);

    // Listen for new shared content while app is running
    ref.listen<SharedContent?>(shareIntentProvider, (previous, next) {
      if (next != null && next.hasUrl) {
        _showShareConfirmDialog(next.extractUrl()!);
        ref.read(shareIntentProvider.notifier).clear();
      }
    });

    return Scaffold(
      appBar: AppBar(
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
        ],
      ),
      body: Column(
        children: [
          // Topic filter chips
          topicsAsync.when(
            data: (topics) => _buildTopicChips(topics, state.selectedTopicId),
            loading: () => const SizedBox.shrink(),
            error: (e, s) => const SizedBox.shrink(),
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
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showAddOptions,
        icon: const Icon(Icons.add),
        label: const Text('Add'),
      ),
    );
  }

  Widget _buildTopicChips(List<Topic> topics, int? selectedTopicId) {
    if (topics.isEmpty) return const SizedBox.shrink();

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
              selected: selectedTopicId == null,
              onSelected: (_) {
                ref.read(itemsProvider.notifier).setTopicFilter(null);
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
        return Slidable(
          key: ValueKey(item.id),
          endActionPane: ActionPane(
            motion: const ScrollMotion(),
            children: [
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
          child: ItemCard(
            item: item,
            onTap: () => context.push('/item/${item.id}'),
          ),
        );
      },
    );
  }
}
