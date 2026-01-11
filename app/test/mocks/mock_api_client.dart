/// Mock API Client for testing
library;

import 'package:vibedinsight/api/api_client.dart';
import 'package:vibedinsight/models/content_item.dart';
import '../fixtures/test_fixtures.dart';

/// Mock implementation of ApiClient for testing
class MockApiClient extends ApiClient {
  bool shouldFail = false;
  String? failureMessage;
  List<ContentItem> itemsToReturn = [];
  ContentItem? singleItemToReturn;
  List<Topic> topicsToReturn = [];

  // Track method calls for verification
  final List<String> methodCalls = [];
  final Map<String, dynamic> lastCallParams = {};

  MockApiClient() : super();

  void reset() {
    shouldFail = false;
    failureMessage = null;
    itemsToReturn = [];
    singleItemToReturn = null;
    topicsToReturn = [];
    methodCalls.clear();
    lastCallParams.clear();
  }

  void setFailure([String message = 'Mock API Error']) {
    shouldFail = true;
    failureMessage = message;
  }

  @override
  Future<bool> healthCheck() async {
    methodCalls.add('healthCheck');
    if (shouldFail) throw Exception(failureMessage);
    return true;
  }

  @override
  Future<PaginatedItems> getItems({
    int page = 1,
    int pageSize = 20,
    int? topicId,
    String? search,
    bool favoritesOnly = false,
    bool unreadOnly = false,
    bool archivedOnly = false,
    SortField sortBy = SortField.date,
    SortOrder sortOrder = SortOrder.desc,
  }) async {
    methodCalls.add('getItems');
    lastCallParams.addAll({
      'page': page,
      'pageSize': pageSize,
      'topicId': topicId,
      'search': search,
      'favoritesOnly': favoritesOnly,
      'unreadOnly': unreadOnly,
      'archivedOnly': archivedOnly,
      'sortBy': sortBy,
      'sortOrder': sortOrder,
    });

    if (shouldFail) throw Exception(failureMessage);

    return PaginatedItems(
      items: itemsToReturn,
      total: itemsToReturn.length,
      page: page,
      pageSize: pageSize,
      pages: (itemsToReturn.length / pageSize).ceil().clamp(1, 100),
    );
  }

  @override
  Future<ContentItemWithRelations> getItemWithRelations(int id) async {
    methodCalls.add('getItemWithRelations');
    lastCallParams['id'] = id;

    if (shouldFail) throw Exception(failureMessage);

    final item = singleItemToReturn ?? TestItems.completedItem;
    return ContentItemWithRelations(
      id: item.id,
      contentType: item.contentType,
      status: item.status,
      url: item.url,
      title: item.title,
      source: item.source,
      rawText: item.rawText,
      summary: item.summary,
      isFavorite: item.isFavorite,
      isRead: item.isRead,
      isArchived: item.isArchived,
      createdAt: item.createdAt,
      updatedAt: item.updatedAt,
      processedAt: item.processedAt,
      topics: item.topics,
      relatedItems: TestRelatedItems.all,
    );
  }

  @override
  Future<ContentItem> ingestUrl(String url) async {
    methodCalls.add('ingestUrl');
    lastCallParams['url'] = url;

    if (shouldFail) throw Exception(failureMessage);

    return singleItemToReturn ?? TestItems.pendingItem;
  }

  @override
  Future<ContentItem> ingestText({
    required String title,
    required String text,
    String contentType = 'note',
  }) async {
    methodCalls.add('ingestText');
    lastCallParams.addAll({'title': title, 'text': text});

    if (shouldFail) throw Exception(failureMessage);

    return singleItemToReturn ?? TestItems.noteItem;
  }

  @override
  Future<ContentItem> toggleFavorite(int id) async {
    methodCalls.add('toggleFavorite');
    lastCallParams['id'] = id;

    if (shouldFail) throw Exception(failureMessage);

    final item = singleItemToReturn ?? TestItems.completedItem;
    return item.copyWith(isFavorite: !item.isFavorite);
  }

  @override
  Future<ContentItem> toggleRead(int id) async {
    methodCalls.add('toggleRead');
    lastCallParams['id'] = id;

    if (shouldFail) throw Exception(failureMessage);

    final item = singleItemToReturn ?? TestItems.completedItem;
    return item.copyWith(isRead: !item.isRead);
  }

  @override
  Future<ContentItem> toggleArchive(int id) async {
    methodCalls.add('toggleArchive');
    lastCallParams['id'] = id;

    if (shouldFail) throw Exception(failureMessage);

    final item = singleItemToReturn ?? TestItems.completedItem;
    return item.copyWith(isArchived: !item.isArchived);
  }

  @override
  Future<void> deleteItem(int id) async {
    methodCalls.add('deleteItem');
    lastCallParams['id'] = id;

    if (shouldFail) throw Exception(failureMessage);
  }

  @override
  Future<List<int>> bulkDeleteItems(List<int> ids) async {
    methodCalls.add('bulkDeleteItems');
    lastCallParams['ids'] = ids;

    if (shouldFail) throw Exception(failureMessage);

    return ids;
  }

  @override
  Future<List<ContentItem>> bulkMarkRead(List<int> ids) async {
    methodCalls.add('bulkMarkRead');
    lastCallParams['ids'] = ids;

    if (shouldFail) throw Exception(failureMessage);

    return ids
        .map((id) => ContentItem(
              id: id,
              contentType: ContentType.link,
              status: ProcessingStatus.completed,
              isRead: true,
              createdAt: DateTime.now(),
            ))
        .toList();
  }

  @override
  Future<List<ContentItem>> bulkArchive(List<int> ids) async {
    methodCalls.add('bulkArchive');
    lastCallParams['ids'] = ids;

    if (shouldFail) throw Exception(failureMessage);

    return ids
        .map((id) => ContentItem(
              id: id,
              contentType: ContentType.link,
              status: ProcessingStatus.completed,
              isArchived: true,
              createdAt: DateTime.now(),
            ))
        .toList();
  }

  @override
  Future<List<Topic>> getTopics() async {
    methodCalls.add('getTopics');

    if (shouldFail) throw Exception(failureMessage);

    return topicsToReturn.isEmpty ? TestTopics.all : topicsToReturn;
  }

  @override
  Future<List<WeeklySummaryListItem>> getWeeklySummaries({int limit = 10}) async {
    methodCalls.add('getWeeklySummaries');

    if (shouldFail) throw Exception(failureMessage);

    return [TestWeeklySummaries.listItem];
  }

  @override
  Future<WeeklySummary> getWeeklySummary(int id) async {
    methodCalls.add('getWeeklySummary');
    lastCallParams['id'] = id;

    if (shouldFail) throw Exception(failureMessage);

    return TestWeeklySummaries.summaryWithContent;
  }

  @override
  Future<WeeklySummary> generateWeeklySummary(int id) async {
    methodCalls.add('generateWeeklySummary');
    lastCallParams['id'] = id;

    if (shouldFail) throw Exception(failureMessage);

    return TestWeeklySummaries.summaryWithContent;
  }
}
