import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/models/content_item.dart';

import '../../fixtures/test_fixtures.dart';

void main() {
  group('ContentType', () {
    test('fromString returns correct enum value', () {
      expect(ContentType.fromString('link'), ContentType.link);
      expect(ContentType.fromString('newsletter'), ContentType.newsletter);
      expect(ContentType.fromString('pdf'), ContentType.pdf);
      expect(ContentType.fromString('note'), ContentType.note);
    });

    test('fromString returns link for unknown value', () {
      expect(ContentType.fromString('unknown'), ContentType.link);
      expect(ContentType.fromString(''), ContentType.link);
    });
  });

  group('ProcessingStatus', () {
    test('fromString returns correct enum value', () {
      expect(ProcessingStatus.fromString('pending'), ProcessingStatus.pending);
      expect(
          ProcessingStatus.fromString('processing'), ProcessingStatus.processing);
      expect(
          ProcessingStatus.fromString('completed'), ProcessingStatus.completed);
      expect(ProcessingStatus.fromString('failed'), ProcessingStatus.failed);
    });

    test('fromString returns pending for unknown value', () {
      expect(ProcessingStatus.fromString('unknown'), ProcessingStatus.pending);
    });
  });

  group('SortField', () {
    test('displayName returns correct strings', () {
      expect(SortField.date.displayName, 'Date');
      expect(SortField.title.displayName, 'Title');
      expect(SortField.status.displayName, 'Status');
    });
  });

  group('SortOrder', () {
    test('displayName returns correct strings', () {
      expect(SortOrder.asc.displayName, 'Ascending');
      expect(SortOrder.desc.displayName, 'Descending');
    });
  });

  group('Topic', () {
    test('fromJson creates correct Topic', () {
      final topic = Topic.fromJson(TestTopics.topic1Json);

      expect(topic.id, 1);
      expect(topic.name, 'Technology');
      expect(topic.createdAt, DateTime(2024, 1, 1));
    });

    test('toJson creates correct map', () {
      final json = TestTopics.topic1.toJson();

      expect(json['id'], 1);
      expect(json['name'], 'Technology');
      expect(json['created_at'], isNotNull);
    });
  });

  group('ContentItem', () {
    test('fromJson creates correct ContentItem', () {
      final item = ContentItem.fromJson(TestItems.completedItemJson);

      expect(item.id, 3);
      expect(item.contentType, ContentType.link);
      expect(item.status, ProcessingStatus.completed);
      expect(item.url, 'https://example.com/article3');
      expect(item.title, 'Completed Article');
      expect(item.source, 'example.com');
      expect(item.summary, 'This is a summary of the completed article.');
      expect(item.isFavorite, false);
      expect(item.isRead, false);
      expect(item.isArchived, false);
      expect(item.topics.length, 1);
      expect(item.topics.first.name, 'Technology');
    });

    test('copyWith creates modified copy', () {
      final original = TestItems.completedItem;
      final copied = original.copyWith(isFavorite: true, isRead: true);

      expect(copied.id, original.id);
      expect(copied.title, original.title);
      expect(copied.isFavorite, true);
      expect(copied.isRead, true);
      expect(copied.isArchived, original.isArchived);
    });

    test('displayTitle returns title when available', () {
      expect(TestItems.completedItem.displayTitle, 'Completed Article');
    });

    test('displayTitle returns url when title is null', () {
      final item = ContentItem(
        id: 1,
        contentType: ContentType.link,
        status: ProcessingStatus.pending,
        url: 'https://example.com',
        createdAt: DateTime.now(),
      );
      expect(item.displayTitle, 'https://example.com');
    });

    test('displayTitle returns Untitled when both are null', () {
      final item = ContentItem(
        id: 1,
        contentType: ContentType.link,
        status: ProcessingStatus.pending,
        createdAt: DateTime.now(),
      );
      expect(item.displayTitle, 'Untitled');
    });

    test('isProcessing returns true for processing status', () {
      expect(TestItems.processingItem.isProcessing, true);
      expect(TestItems.completedItem.isProcessing, false);
    });

    test('isCompleted returns true for completed status', () {
      expect(TestItems.completedItem.isCompleted, true);
      expect(TestItems.processingItem.isCompleted, false);
    });

    test('hasSummary returns true when summary exists', () {
      expect(TestItems.completedItem.hasSummary, true);
      expect(TestItems.pendingItem.hasSummary, false);
    });
  });

  group('RelationType', () {
    test('fromString handles extends correctly', () {
      expect(RelationType.fromString('extends'), RelationType.extends_);
    });

    test('displayName returns correct strings', () {
      expect(RelationType.related.displayName, 'Related');
      expect(RelationType.extends_.displayName, 'Extends');
      expect(RelationType.contradicts.displayName, 'Contradicts');
      expect(RelationType.similar.displayName, 'Similar');
      expect(RelationType.references.displayName, 'References');
    });
  });

  group('RelatedItem', () {
    test('fromJson creates correct RelatedItem', () {
      final json = {
        'id': 10,
        'title': 'Related Article',
        'source': 'related.com',
        'relation_type': 'related',
        'confidence': 0.85,
      };

      final item = RelatedItem.fromJson(json);

      expect(item.id, 10);
      expect(item.title, 'Related Article');
      expect(item.source, 'related.com');
      expect(item.relationType, RelationType.related);
      expect(item.confidence, 0.85);
    });

    test('displayTitle returns title when available', () {
      expect(TestRelatedItems.relatedItem.displayTitle, 'Related Article');
    });
  });

  group('PaginatedItems', () {
    test('fromJson creates correct PaginatedItems', () {
      final paginated = PaginatedItems.fromJson(TestItems.paginatedResponseJson);

      expect(paginated.items.length, 1);
      expect(paginated.total, 1);
      expect(paginated.page, 1);
      expect(paginated.pageSize, 20);
      expect(paginated.pages, 1);
    });
  });

  group('WeeklySummary', () {
    test('hasSummary returns true when summary exists', () {
      expect(TestWeeklySummaries.summaryWithContent.hasSummary, true);
      expect(TestWeeklySummaries.summaryWithoutContent.hasSummary, false);
    });

    test('weekLabel formats correctly', () {
      final label = TestWeeklySummaries.summaryWithContent.weekLabel;
      expect(label, '1.–7. Jan');
    });
  });
}
