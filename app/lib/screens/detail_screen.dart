import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:timeago/timeago.dart' as timeago;
import 'package:url_launcher/url_launcher.dart';

import '../models/content_item.dart';
import '../providers/api_provider.dart';
import '../providers/items_provider.dart';

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
    _tabController = TabController(length: 2, vsync: this);
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

  Widget _buildContent(ContentItem item) {
    return Scaffold(
      appBar: AppBar(
        title: Text(item.displayTitle, maxLines: 1),
        actions: [
          if (item.url != null)
            IconButton(
              icon: const Icon(Icons.open_in_browser),
              onPressed: () => _openUrl(item.url!),
            ),
          PopupMenuButton(
            itemBuilder: (context) => [
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
          tabs: const [
            Tab(text: 'Summary'),
            Tab(text: 'Original'),
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
      backgroundColor: color.withOpacity(0.1),
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
}
