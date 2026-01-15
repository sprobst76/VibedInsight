/// Test fixtures - sample data for testing
library;

import 'package:vibedinsight/models/content_item.dart';

/// Sample Topics
class TestTopics {
  static final topic1 = Topic(
    id: 1,
    name: 'Technology',
    createdAt: DateTime(2024, 1, 1),
  );

  static final topic2 = Topic(
    id: 2,
    name: 'Science',
    createdAt: DateTime(2024, 1, 2),
  );

  static final topic3 = Topic(
    id: 3,
    name: 'Business',
    createdAt: DateTime(2024, 1, 3),
  );

  static List<Topic> get all => [topic1, topic2, topic3];

  static Map<String, dynamic> get topic1Json => {
        'id': 1,
        'name': 'Technology',
        'created_at': '2024-01-01T00:00:00.000',
      };
}

/// Sample ContentItems
class TestItems {
  static ContentItem get pendingItem => ContentItem(
        id: 1,
        contentType: ContentType.link,
        status: ProcessingStatus.pending,
        url: 'https://example.com/article1',
        title: 'Pending Article',
        createdAt: DateTime(2024, 1, 1),
      );

  static ContentItem get processingItem => ContentItem(
        id: 2,
        contentType: ContentType.link,
        status: ProcessingStatus.processing,
        url: 'https://example.com/article2',
        title: 'Processing Article',
        createdAt: DateTime(2024, 1, 2),
      );

  static ContentItem get completedItem => ContentItem(
        id: 3,
        contentType: ContentType.link,
        status: ProcessingStatus.completed,
        url: 'https://example.com/article3',
        title: 'Completed Article',
        source: 'example.com',
        summary: 'This is a summary of the completed article.',
        createdAt: DateTime(2024, 1, 3),
        processedAt: DateTime(2024, 1, 3, 12, 0),
        topics: [TestTopics.topic1],
      );

  static ContentItem get favoriteItem => ContentItem(
        id: 4,
        contentType: ContentType.link,
        status: ProcessingStatus.completed,
        url: 'https://example.com/favorite',
        title: 'Favorite Article',
        isFavorite: true,
        createdAt: DateTime(2024, 1, 4),
      );

  static ContentItem get readItem => ContentItem(
        id: 5,
        contentType: ContentType.link,
        status: ProcessingStatus.completed,
        url: 'https://example.com/read',
        title: 'Read Article',
        isRead: true,
        createdAt: DateTime(2024, 1, 5),
      );

  static ContentItem get archivedItem => ContentItem(
        id: 6,
        contentType: ContentType.link,
        status: ProcessingStatus.completed,
        url: 'https://example.com/archived',
        title: 'Archived Article',
        isArchived: true,
        createdAt: DateTime(2024, 1, 6),
      );

  static ContentItem get noteItem => ContentItem(
        id: 7,
        contentType: ContentType.note,
        status: ProcessingStatus.completed,
        title: 'My Note',
        rawText: 'This is the content of my note.',
        summary: 'Note summary',
        createdAt: DateTime(2024, 1, 7),
      );

  static ContentItem get failedItem => ContentItem(
        id: 8,
        contentType: ContentType.link,
        status: ProcessingStatus.failed,
        url: 'https://example.com/failed',
        title: 'Failed Article',
        createdAt: DateTime(2024, 1, 8),
      );

  static List<ContentItem> get sampleList => [
        completedItem,
        pendingItem,
        processingItem,
        favoriteItem,
        readItem,
      ];

  static Map<String, dynamic> get completedItemJson => {
        'id': 3,
        'content_type': 'link',
        'status': 'completed',
        'url': 'https://example.com/article3',
        'title': 'Completed Article',
        'source': 'example.com',
        'summary': 'This is a summary of the completed article.',
        'is_favorite': false,
        'is_read': false,
        'is_archived': false,
        'created_at': '2024-01-03T00:00:00.000',
        'processed_at': '2024-01-03T12:00:00.000',
        'topics': [TestTopics.topic1Json],
      };

  static Map<String, dynamic> get paginatedResponseJson => {
        'items': [completedItemJson],
        'total': 1,
        'page': 1,
        'page_size': 20,
        'pages': 1,
      };
}

/// Sample RelatedItems
class TestRelatedItems {
  static RelatedItem get relatedItem => RelatedItem(
        id: '10',
        title: 'Related Article',
        source: 'related.com',
        relationType: RelationType.related,
        confidence: 0.85,
      );

  static RelatedItem get similarItem => RelatedItem(
        id: '11',
        title: 'Similar Article',
        source: 'similar.com',
        relationType: RelationType.similar,
        confidence: 0.92,
      );

  static List<RelatedItem> get all => [relatedItem, similarItem];
}

/// Sample WeeklySummaries
class TestWeeklySummaries {
  static WeeklySummary get summaryWithContent => WeeklySummary(
        id: 1,
        weekStart: DateTime(2024, 1, 1),
        weekEnd: DateTime(2024, 1, 7),
        summary: 'This week covered various technology topics...',
        keyInsights: ['Key insight 1', 'Key insight 2'],
        topTopics: ['Technology', 'AI'],
        itemsCount: 10,
        itemsProcessed: 8,
        createdAt: DateTime(2024, 1, 7),
        generatedAt: DateTime(2024, 1, 7, 12, 0),
      );

  static WeeklySummary get summaryWithoutContent => WeeklySummary(
        id: 2,
        weekStart: DateTime(2024, 1, 8),
        weekEnd: DateTime(2024, 1, 14),
        itemsCount: 5,
        itemsProcessed: 3,
        createdAt: DateTime(2024, 1, 14),
      );

  static WeeklySummaryListItem get listItem => WeeklySummaryListItem(
        id: 1,
        weekStart: DateTime(2024, 1, 1),
        weekEnd: DateTime(2024, 1, 7),
        itemsCount: 10,
        itemsProcessed: 8,
        hasSummary: true,
      );
}
