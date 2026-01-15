import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/content_item.dart';
import '../providers/weekly_provider.dart';

class WeeklyScreen extends ConsumerStatefulWidget {
  const WeeklyScreen({super.key});

  @override
  ConsumerState<WeeklyScreen> createState() => _WeeklyScreenState();
}

class _WeeklyScreenState extends ConsumerState<WeeklyScreen> {
  bool _summaryExpanded = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(weeklyProvider.notifier).loadCurrentWeek();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(weeklyProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Wochenzusammenfassung'),
        actions: [
          if (state.currentWeek?.hasSummary == true)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: state.isGenerating
                  ? null
                  : () => ref.read(weeklyProvider.notifier).generateCurrentWeekSummary(),
              tooltip: 'Neu generieren',
            ),
        ],
      ),
      body: _buildBody(state),
    );
  }

  Widget _buildBody(WeeklyState state) {
    if (state.isLoading && state.currentWeek == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.error != null && state.currentWeek == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text('Fehler: ${state.error}'),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => ref.read(weeklyProvider.notifier).loadCurrentWeek(),
              child: const Text('Erneut versuchen'),
            ),
          ],
        ),
      );
    }

    final summary = state.currentWeek;
    if (summary == null) {
      return const Center(child: Text('Keine Daten'));
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(weeklyProvider.notifier).loadCurrentWeek(),
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(summary),
            const SizedBox(height: 16),
            if (summary.hasSummary) ...[
              // TL;DR section - most prominent
              if (summary.hasTldr) ...[
                _buildTldrSection(summary),
                const SizedBox(height: 20),
              ],
              // Topic Clusters
              if (summary.hasTopicClusters) ...[
                _buildTopicClustersSection(summary),
                const SizedBox(height: 20),
              ],
              // Connections
              if (summary.hasConnections) ...[
                _buildConnectionsSection(summary),
                const SizedBox(height: 20),
              ],
              // Full Summary (collapsible)
              _buildFullSummarySection(summary),
              const SizedBox(height: 20),
              // Key Insights
              if (summary.keyInsights.isNotEmpty) ...[
                _buildInsightsSection(summary),
                const SizedBox(height: 20),
              ],
              // Top Topics (as chips)
              if (summary.topTopics.isNotEmpty) _buildTopicsSection(summary),
            ] else
              _buildEmptySummary(summary, state.isGenerating),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(WeeklySummary summary) {
    final dateFormat = DateFormat('d. MMM', 'de_DE');
    final weekRange =
        '${dateFormat.format(summary.weekStart)} - ${dateFormat.format(summary.weekEnd)}';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.calendar_today,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Aktuelle Woche',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        weekRange,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context).colorScheme.outline,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                _buildStatChip(
                  Icons.article_outlined,
                  '${summary.itemsCount} Artikel',
                ),
                const SizedBox(width: 8),
                _buildStatChip(
                  Icons.check_circle_outline,
                  '${summary.itemsProcessed} verarbeitet',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16),
          const SizedBox(width: 4),
          Text(label, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }

  Widget _buildTldrSection(WeeklySummary summary) {
    return Card(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.lightbulb,
                  color: Theme.of(context).colorScheme.onPrimaryContainer,
                ),
                const SizedBox(width: 8),
                Text(
                  'TL;DR',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onPrimaryContainer,
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              summary.tldr ?? '',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                  ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopicClustersSection(WeeklySummary summary) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.category,
              color: Theme.of(context).colorScheme.secondary,
            ),
            const SizedBox(width: 8),
            Text(
              'Themen-Cluster',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: summary.topicClusters.map((cluster) {
            return _TopicClusterCard(cluster: cluster);
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildConnectionsSection(WeeklySummary summary) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.link,
              color: Theme.of(context).colorScheme.tertiary,
            ),
            const SizedBox(width: 8),
            Text(
              'Verbindungen',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: summary.connections.map((connection) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.swap_horiz,
                        size: 18,
                        color: Theme.of(context).colorScheme.tertiary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          connection,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFullSummarySection(WeeklySummary summary) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => setState(() => _summaryExpanded = !_summaryExpanded),
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                Icon(
                  Icons.description,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Zusammenfassung',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Icon(
                  _summaryExpanded ? Icons.expand_less : Icons.expand_more,
                  color: Theme.of(context).colorScheme.outline,
                ),
              ],
            ),
          ),
        ),
        AnimatedCrossFade(
          firstChild: const SizedBox.shrink(),
          secondChild: Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  summary.summary ?? '',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
            ),
          ),
          crossFadeState: _summaryExpanded
              ? CrossFadeState.showSecond
              : CrossFadeState.showFirst,
          duration: const Duration(milliseconds: 200),
        ),
      ],
    );
  }

  Widget _buildInsightsSection(WeeklySummary summary) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.auto_awesome,
              color: Theme.of(context).colorScheme.secondary,
            ),
            const SizedBox(width: 8),
            Text(
              'Key Insights',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        ...summary.keyInsights.map((insight) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Card(
                child: ListTile(
                  leading: Icon(
                    Icons.star,
                    color: Theme.of(context).colorScheme.secondary,
                    size: 20,
                  ),
                  title: Text(insight),
                ),
              ),
            )),
      ],
    );
  }

  Widget _buildTopicsSection(WeeklySummary summary) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.tag,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(width: 8),
            Text(
              'Top Topics',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: summary.topTopics
              .map((topic) => Chip(
                    label: Text(topic),
                    backgroundColor:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                  ))
              .toList(),
        ),
      ],
    );
  }

  Widget _buildEmptySummary(WeeklySummary summary, bool isGenerating) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.auto_awesome,
              size: 64,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 16),
            Text(
              'Keine Zusammenfassung vorhanden',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              summary.itemsProcessed > 0
                  ? 'Erstelle eine KI-Zusammenfassung deiner ${summary.itemsProcessed} Artikel'
                  : 'Fuege zuerst Inhalte hinzu',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            if (summary.itemsProcessed > 0)
              FilledButton.icon(
                onPressed: isGenerating
                    ? null
                    : () => ref.read(weeklyProvider.notifier).generateCurrentWeekSummary(),
                icon: isGenerating
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.auto_awesome),
                label: Text(isGenerating ? 'Wird generiert...' : 'Zusammenfassung erstellen'),
              ),
          ],
        ),
      ),
    );
  }
}

class _TopicClusterCard extends StatelessWidget {
  final TopicCluster cluster;

  const _TopicClusterCard({required this.cluster});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          // Could filter inbox by this topic in the future
        },
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.folder,
                    size: 18,
                    color: Theme.of(context).colorScheme.secondary,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    cluster.name,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.secondaryContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${cluster.articleCount} Artikel',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSecondaryContainer,
                      ),
                ),
              ),
              const SizedBox(height: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 200),
                child: Text(
                  cluster.description,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.outline,
                      ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
