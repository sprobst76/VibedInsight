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
                    if (onToggleRead != null) ...[
                      const SizedBox(width: 4),
                      GestureDetector(
                        onTap: onToggleRead,
                        child: Icon(
                          item.isRead ? Icons.mark_email_read : Icons.mark_email_unread,
                          color: item.isRead ? Colors.grey : Theme.of(context).colorScheme.primary,
                          size: 22,
                        ),
                      ),
                    ],
                    if (onToggleFavorite != null) ...[
                      const SizedBox(width: 4),
                      GestureDetector(
                        onTap: onToggleFavorite,
                        child: Icon(
                          item.isFavorite ? Icons.star : Icons.star_border,
                          color: item.isFavorite ? Colors.amber : Colors.grey,
                          size: 24,
                        ),
                      ),
                    ],
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
                    Text(
                      item.source!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.outline,
                          ),
                    ),
                    const Spacer(),
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
