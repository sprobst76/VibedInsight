import 'package:flutter/material.dart';
import 'package:timeago/timeago.dart' as timeago;

import '../models/content_item.dart';

class ItemCard extends StatelessWidget {
  final ContentItem item;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;
  final VoidCallback? onToggleFavorite;
  final VoidCallback? onToggleRead;
  final VoidCallback? onLongPress;
  final Function(int rating)? onSetRating;
  final bool isSelectionMode;
  final bool isSelected;
  final VoidCallback? onToggleSelection;

  const ItemCard({
    super.key,
    required this.item,
    this.onTap,
    this.onDelete,
    this.onToggleFavorite,
    this.onToggleRead,
    this.onLongPress,
    this.onSetRating,
    this.isSelectionMode = false,
    this.isSelected = false,
    this.onToggleSelection,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: isSelected
          ? Theme.of(context).colorScheme.primaryContainer.withAlpha(128)
          : null,
      child: InkWell(
        onTap: isSelectionMode ? onToggleSelection : onTap,
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header row
              Row(
                children: [
                  // Checkbox in selection mode
                  if (isSelectionMode) ...[
                    Checkbox(
                      value: isSelected,
                      onChanged: (_) => onToggleSelection?.call(),
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      visualDensity: VisualDensity.compact,
                    ),
                    const SizedBox(width: 4),
                  ],
                  _buildTypeIcon(),
                  const SizedBox(width: 8),
                  // Unread indicator dot
                  if (!item.isRead && !isSelectionMode) ...[
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primary,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                  ],
                  Expanded(
                    child: Text(
                      item.displayTitle,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: item.isRead ? FontWeight.w500 : FontWeight.w700,
                          ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (!isSelectionMode) ...[
                    _buildStatusIndicator(),
                    // IconButtons (not bare GestureDetectors) give a 44dp+ touch
                    // target and a screen-reader label via `tooltip`.
                    if (onToggleRead != null)
                      IconButton(
                        onPressed: onToggleRead,
                        tooltip: item.isRead
                            ? 'Als ungelesen markieren'
                            : 'Als gelesen markieren',
                        padding: EdgeInsets.zero,
                        visualDensity: VisualDensity.compact,
                        constraints: const BoxConstraints(
                          minWidth: 44,
                          minHeight: 44,
                        ),
                        iconSize: 22,
                        color: item.isRead
                            ? Colors.grey
                            : Theme.of(context).colorScheme.primary,
                        icon: Icon(
                          item.isRead
                              ? Icons.mark_email_read
                              : Icons.mark_email_unread,
                        ),
                      ),
                    if (onToggleFavorite != null)
                      IconButton(
                        onPressed: onToggleFavorite,
                        tooltip: item.isFavorite
                            ? 'Favorit entfernen'
                            : 'Als Favorit markieren',
                        padding: EdgeInsets.zero,
                        visualDensity: VisualDensity.compact,
                        constraints: const BoxConstraints(
                          minWidth: 44,
                          minHeight: 44,
                        ),
                        iconSize: 24,
                        color: item.isFavorite ? Colors.amber : Colors.grey,
                        icon: Icon(
                          item.isFavorite ? Icons.star : Icons.star_border,
                        ),
                      ),
                  ],
                ],
              ),

              // Source and time
              if (item.source != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(
                      Icons.link,
                      size: 14,
                      color: Theme.of(context).colorScheme.outline,
                    ),
                    const SizedBox(width: 4),
                    // Source can be a long URL — keep it to one line so it
                    // truncates instead of overflowing the row.
                    Expanded(
                      child: Text(
                        item.source!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context).colorScheme.outline,
                            ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      timeago.format(item.createdAt),
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.outline,
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
                  children: item.topics.take(5).map((topic) {
                    return Chip(
                      label: Text(topic.name),
                      labelStyle: const TextStyle(fontSize: 11),
                      padding: EdgeInsets.zero,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      visualDensity: VisualDensity.compact,
                    );
                  }).toList(),
                ),
              ],

              // Star rating
              if (!isSelectionMode && onSetRating != null) ...[
                const SizedBox(height: 10),
                Row(
                  children: List.generate(5, (index) {
                    final starValue = index + 1;
                    return Semantics(
                      button: true,
                      selected: starValue <= item.rating,
                      label: 'Mit $starValue von 5 Sternen bewerten',
                      child: GestureDetector(
                        onTap: () =>
                            onSetRating!(item.rating == starValue ? 0 : starValue),
                        child: Padding(
                          padding: const EdgeInsets.all(4),
                          child: Icon(
                            starValue <= item.rating ? Icons.star : Icons.star_border,
                            size: 18,
                            color: starValue <= item.rating
                                ? Colors.amber
                                : Theme.of(context).colorScheme.outlineVariant,
                          ),
                        ),
                      ),
                    );
                  }),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTypeIcon() {
    IconData icon;
    Color color;

    switch (item.contentType) {
      case ContentType.link:
        icon = Icons.link;
        color = Colors.blue;
        break;
      case ContentType.newsletter:
        icon = Icons.email;
        color = Colors.orange;
        break;
      case ContentType.pdf:
        icon = Icons.picture_as_pdf;
        color = Colors.red;
        break;
      case ContentType.note:
        icon = Icons.note;
        color = Colors.green;
        break;
    }

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: color.withAlpha((0.1 * 255).round()),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, size: 20, color: color),
    );
  }

  Widget _buildStatusIndicator() {
    if (item.status == ProcessingStatus.processing) {
      return const SizedBox(
        width: 16,
        height: 16,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }

    if (item.status == ProcessingStatus.failed) {
      return const Icon(Icons.error_outline, color: Colors.red, size: 20);
    }

    if (item.hasSummary) {
      return const Icon(Icons.check_circle, color: Colors.green, size: 20);
    }

    return const SizedBox.shrink();
  }
}
