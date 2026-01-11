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
        title: const Text('Weekly Summary'),
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
            Text('Error: ${state.error}'),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => ref.read(weeklyProvider.notifier).loadCurrentWeek(),
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    final summary = state.currentWeek;
    if (summary == null) {
      return const Center(child: Text('No data'));
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
            const SizedBox(height: 24),
            if (summary.hasSummary) ...[
              _buildSummarySection(summary),
              const SizedBox(height: 24),
              if (summary.keyInsights.isNotEmpty) ...[
                _buildInsightsSection(summary),
                const SizedBox(height: 24),
              ],
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
        '${dateFormat.format(summary.weekStart)} – ${dateFormat.format(summary.weekEnd)}';

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
                        'Current Week',
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
                  '${summary.itemsCount} Items',
                ),
                const SizedBox(width: 8),
                _buildStatChip(
                  Icons.check_circle_outline,
                  '${summary.itemsProcessed} Processed',
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

  Widget _buildSummarySection(WeeklySummary summary) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.summarize,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 8),
            Text(
              'Summary',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              summary.summary ?? '',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
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
              Icons.lightbulb_outline,
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
                    Icons.arrow_right,
                    color: Theme.of(context).colorScheme.secondary,
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
              color: Theme.of(context).colorScheme.tertiary,
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
                        Theme.of(context).colorScheme.tertiaryContainer,
                  ))
              .toList(),
        ),
      ],
    );
  }

  Widget _buildEmptySummary(WeeklySummary summary, bool isGenerating) {
    return Center(
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
            'No summary generated yet',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            summary.itemsProcessed > 0
                ? 'Generate an AI summary of your ${summary.itemsProcessed} processed items'
                : 'Add some content first to generate a summary',
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
              label: Text(isGenerating ? 'Generating...' : 'Generate Summary'),
            ),
        ],
      ),
    );
  }
}
