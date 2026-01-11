import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:timeago/timeago.dart' as timeago;
import 'package:url_launcher/url_launcher.dart';

import '../models/content_item.dart';
import '../providers/api_provider.dart';
import '../providers/items_provider.dart';
import '../widgets/edit_item_dialog.dart';

class DetailScreen extends ConsumerStatefulWidget {
  final int itemId;

  const DetailScreen({super.key, required this.itemId});

  @override
  ConsumerState<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends ConsumerState<DetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _openUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  Future<void> _reprocess(ContentItem item) async {
    final apiClient = ref.read(apiClientProvider);
    final updated = await apiClient.reprocessItem(item.id);
    ref.read(itemsProvider.notifier).updateItem(updated);
    ref.invalidate(itemDetailProvider(widget.itemId));
  }

  Future<void> _toggleFavorite(ContentItem item) async {
    try {
      final apiClient = ref.read(apiClientProvider);
      final updated = await apiClient.toggleFavorite(item.id);
      ref.read(itemsProvider.notifier).updateItem(updated);
      ref.invalidate(itemDetailProvider(widget.itemId));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  Future<void> _toggleRead(ContentItem item) async {
    try {
      final apiClient = ref.read(apiClientProvider);
      final updated = await apiClient.toggleRead(item.id);
      ref.read(itemsProvider.notifier).updateItem(updated);
      ref.invalidate(itemDetailProvider(widget.itemId));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  Future<void> _editItem(ContentItem item) async {
    final result = await showDialog<EditItemResult>(
      context: context,
      builder: (context) => EditItemDialog(item: item),
    );

    if (result != null && mounted) {
      try {
        final apiClient = ref.read(apiClientProvider);
        final updated = await apiClient.updateItem(
          item.id,
          title: result.title,
          summary: result.summary,
        );
        ref.read(itemsProvider.notifier).updateItem(updated);
        ref.invalidate(itemDetailProvider(widget.itemId));

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Item updated')),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final itemAsync = ref.watch(itemDetailProvider(widget.itemId));

    return itemAsync.when(
      loading: () => Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (error, stack) => Scaffold(
        appBar: AppBar(),
        body: Center(child: Text('Error: $error')),
      ),
      data: (item) => _buildContent(item),
    );
  }

  Widget _buildContent(ContentItemWithRelations item) {
    return Scaffold(
      appBar: AppBar(
        title: Text(item.displayTitle, maxLines: 1),
        actions: [
          IconButton(
            icon: Icon(
              item.isRead ? Icons.mark_email_read : Icons.mark_email_unread,
              color: item.isRead ? null : Theme.of(context).colorScheme.primary,
            ),
            tooltip: item.isRead ? 'Mark as unread' : 'Mark as read',
            onPressed: () => _toggleRead(item),
          ),
          IconButton(
            icon: Icon(
              item.isFavorite ? Icons.star : Icons.star_border,
              color: item.isFavorite ? Colors.amber : null,
            ),
            onPressed: () => _toggleFavorite(item),
          ),
          if (item.url != null)
            IconButton(
              icon: const Icon(Icons.open_in_browser),
              onPressed: () => _openUrl(item.url!),
            ),
          PopupMenuButton(
            itemBuilder: (context) => [
              PopupMenuItem(
                onTap: () => _editItem(item),
                child: const Row(
                  children: [
                    Icon(Icons.edit),
                    SizedBox(width: 8),
                    Text('Edit'),
                  ],
                ),
              ),
              PopupMenuItem(
                onTap: () => _reprocess(item),
                child: const Row(
                  children: [
                    Icon(Icons.refresh),
                    SizedBox(width: 8),
                    Text('Reprocess'),
                  ],
                ),
              ),
              if (item.summary != null)
                PopupMenuItem(
                  onTap: () {
                    Clipboard.setData(ClipboardData(text: item.summary!));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Summary copied')),
                    );
                  },
                  child: const Row(
                    children: [
                      Icon(Icons.copy),
                      SizedBox(width: 8),
                      Text('Copy Summary'),
                    ],
                  ),
                ),
            ],
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            const Tab(text: 'Summary'),
            const Tab(text: 'Original'),
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Related'),
                  if (item.relatedItems.isNotEmpty) ...[
                    const SizedBox(width: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primaryContainer,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '${item.relatedItems.length}',
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onPrimaryContainer,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          // Metadata header
          _buildHeader(item),

          // Tab content
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildSummaryTab(item),
                _buildOriginalTab(item),
                _buildRelatedTab(item),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(ContentItem item) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status row
          Row(
            children: [
              _buildStatusChip(item),
              const Spacer(),
              Text(
                timeago.format(item.createdAt),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),

          // Source
          if (item.source != null) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.link, size: 16),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    item.source!,
                    style: Theme.of(context).textTheme.bodySmall,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],

          // Topics
          if (item.topics.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: item.topics.map((topic) {
                return Chip(
                  label: Text(topic.name),
                  labelStyle: const TextStyle(fontSize: 12),
                  padding: EdgeInsets.zero,
                  visualDensity: VisualDensity.compact,
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatusChip(ContentItem item) {
    Color color;
    String label;
    IconData icon;

    switch (item.status) {
      case ProcessingStatus.pending:
        color = Colors.orange;
        label = 'Pending';
        icon = Icons.schedule;
        break;
      case ProcessingStatus.processing:
        color = Colors.blue;
        label = 'Processing';
        icon = Icons.sync;
        break;
      case ProcessingStatus.completed:
        color = Colors.green;
        label = 'Completed';
        icon = Icons.check_circle;
        break;
      case ProcessingStatus.failed:
        color = Colors.red;
        label = 'Failed';
        icon = Icons.error;
        break;
    }

    return Chip(
      avatar: Icon(icon, size: 16, color: color),
      label: Text(label),
      labelStyle: TextStyle(fontSize: 12, color: color),
      backgroundColor: color.withAlpha((0.1 * 255).round()),
      side: BorderSide.none,
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildSummaryTab(ContentItem item) {
    if (item.status == ProcessingStatus.processing) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Generating summary...'),
          ],
        ),
      );
    }

    if (!item.hasSummary) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.summarize_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 16),
            const Text('No summary available'),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => _reprocess(item),
              icon: const Icon(Icons.refresh),
              label: const Text('Generate Summary'),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: SelectableText(
        item.summary!,
        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              height: 1.6,
            ),
      ),
    );
  }

  Widget _buildOriginalTab(ContentItem item) {
    if (item.rawText == null || item.rawText!.isEmpty) {
      return const Center(child: Text('No content available'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: SelectableText(
        item.rawText!,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              height: 1.5,
            ),
      ),
    );
  }

  Widget _buildRelatedTab(ContentItemWithRelations item) {
    if (item.relatedItems.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.hub_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 16),
            Text(
              'No related items',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Items with shared topics will appear here',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: item.relatedItems.length,
      itemBuilder: (context, index) {
        final related = item.relatedItems[index];
        return _buildRelatedItemCard(related);
      },
    );
  }

  Widget _buildRelatedItemCard(RelatedItem related) {
    // Color based on relation type
    Color relationColor;
    IconData relationIcon;

    switch (related.relationType) {
      case RelationType.extends_:
        relationColor = Colors.blue;
        relationIcon = Icons.add_circle_outline;
        break;
      case RelationType.contradicts:
        relationColor = Colors.red;
        relationIcon = Icons.cancel_outlined;
        break;
      case RelationType.similar:
        relationColor = Colors.green;
        relationIcon = Icons.compare_arrows;
        break;
      case RelationType.references:
        relationColor = Colors.purple;
        relationIcon = Icons.format_quote;
        break;
      case RelationType.related:
        relationColor = Colors.grey;
        relationIcon = Icons.link;
        break;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () => context.push('/item/${related.id}'),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // Relation type icon
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: relationColor.withAlpha(25),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(relationIcon, color: relationColor, size: 24),
              ),
              const SizedBox(width: 16),

              // Title and metadata
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      related.displayTitle,
                      style: Theme.of(context).textTheme.titleSmall,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: relationColor.withAlpha(25),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            related.relationType.displayName,
                            style: TextStyle(
                              fontSize: 11,
                              color: relationColor,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                        if (related.source != null) ...[
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              related.source!,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: Theme.of(context).colorScheme.outline,
                                  ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ],
                    ),
                    // Confidence indicator
                    if (related.confidence < 1.0) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          SizedBox(
                            width: 60,
                            child: LinearProgressIndicator(
                              value: related.confidence,
                              backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
                              color: relationColor,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '${(related.confidence * 100).toInt()}%',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Theme.of(context).colorScheme.outline,
                                ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),

              // Arrow
              Icon(
                Icons.chevron_right,
                color: Theme.of(context).colorScheme.outline,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
