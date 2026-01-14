import 'package:dio/dio.dart';

import '../config/api_config.dart';
import '../models/content_item.dart';

class ApiClient {
  late final Dio _dio;

  ApiClient() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: ApiConfig.connectTimeout,
        receiveTimeout: ApiConfig.receiveTimeout,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    // Add logging interceptor for debugging
    _dio.interceptors.add(
      LogInterceptor(
        requestBody: true,
        responseBody: true,
        error: true,
      ),
    );
  }

  // Health Check
  Future<bool> healthCheck() async {
    try {
      final response = await _dio.get('/health');
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  // Items
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
    final response = await _dio.get(
      '/items',
      queryParameters: {
        'page': page,
        'page_size': pageSize,
        if (topicId != null) 'topic_id': topicId,
        if (search != null && search.isNotEmpty) 'search': search,
        if (favoritesOnly) 'favorites_only': true,
        if (unreadOnly) 'unread_only': true,
        if (archivedOnly) 'archived_only': true,
        'sort_by': sortBy.name,
        'sort_order': sortOrder.name,
      },
    );
    return PaginatedItems.fromJson(response.data);
  }

  Future<ContentItem> getItem(int id) async {
    final response = await _dio.get('/items/$id');
    return ContentItem.fromJson(response.data);
  }

  Future<ContentItemWithRelations> getItemWithRelations(int id) async {
    final response = await _dio.get('/items/$id/relations');
    return ContentItemWithRelations.fromJson(response.data);
  }

  Future<ContentItem> updateItem(
    int id, {
    String? title,
    String? summary,
    List<int>? topicIds,
  }) async {
    final data = <String, dynamic>{};
    if (title != null) data['title'] = title;
    if (summary != null) data['summary'] = summary;
    if (topicIds != null) data['topic_ids'] = topicIds;

    final response = await _dio.patch('/items/$id', data: data);
    return ContentItem.fromJson(response.data);
  }

  Future<ContentItem> toggleFavorite(int id) async {
    final response = await _dio.post('/items/$id/favorite');
    return ContentItem.fromJson(response.data);
  }

  Future<ContentItem> toggleRead(int id) async {
    final response = await _dio.post('/items/$id/read');
    return ContentItem.fromJson(response.data);
  }

  Future<ContentItem> toggleArchive(int id) async {
    final response = await _dio.post('/items/$id/archive');
    return ContentItem.fromJson(response.data);
  }

  Future<void> deleteItem(int id) async {
    await _dio.delete('/items/$id');
  }

  // Bulk Operations
  Future<List<int>> bulkDeleteItems(List<int> ids) async {
    final response = await _dio.post(
      '/items/bulk/delete',
      data: {'ids': ids},
    );
    return (response.data['deleted_ids'] as List).cast<int>();
  }

  Future<List<ContentItem>> bulkMarkRead(List<int> ids) async {
    final response = await _dio.post(
      '/items/bulk/read',
      data: {'ids': ids},
    );
    return (response.data as List)
        .map((e) => ContentItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<ContentItem>> bulkArchive(List<int> ids) async {
    final response = await _dio.post(
      '/items/bulk/archive',
      data: {'ids': ids},
    );
    return (response.data as List)
        .map((e) => ContentItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // Ingest
  Future<ContentItem> ingestUrl(String url) async {
    final response = await _dio.post(
      '/ingest/url',
      data: {'url': url},
    );
    return ContentItem.fromJson(response.data);
  }

  Future<ContentItem> ingestText({
    required String title,
    required String text,
    String contentType = 'note',
  }) async {
    final response = await _dio.post(
      '/ingest/text',
      data: {
        'title': title,
        'text': text,
        'content_type': contentType,
      },
    );
    return ContentItem.fromJson(response.data);
  }

  Future<ContentItem> reprocessItem(int id) async {
    final response = await _dio.post('/ingest/$id/reprocess');
    return ContentItem.fromJson(response.data);
  }

  // Topics
  Future<List<Topic>> getTopics() async {
    final response = await _dio.get('/topics');
    return (response.data as List)
        .map((e) => Topic.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Topic> createTopic(String name) async {
    final response = await _dio.post(
      '/topics',
      data: {'name': name},
    );
    return Topic.fromJson(response.data);
  }

  Future<void> deleteTopic(int id) async {
    await _dio.delete('/topics/$id');
  }

  // Weekly Summaries
  Future<List<WeeklySummaryListItem>> getWeeklySummaries({int limit = 10}) async {
    final response = await _dio.get(
      '/weekly',
      queryParameters: {'limit': limit},
    );
    return (response.data as List)
        .map((e) => WeeklySummaryListItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<WeeklySummary> getCurrentWeekSummary() async {
    final response = await _dio.get('/weekly/current');
    return WeeklySummary.fromJson(response.data);
  }

  Future<WeeklySummary> getWeeklySummary(int id) async {
    final response = await _dio.get('/weekly/$id');
    return WeeklySummary.fromJson(response.data);
  }

  Future<WeeklySummary> generateWeeklySummary(int id) async {
    final response = await _dio.post('/weekly/$id/generate');
    return WeeklySummary.fromJson(response.data);
  }

  Future<WeeklySummary> generateCurrentWeekSummary() async {
    final response = await _dio.post('/weekly/generate-current');
    return WeeklySummary.fromJson(response.data);
  }

  // Graph Data
  Future<GraphData> getGraphData() async {
    final response = await _dio.get('/items/graph/data');
    return GraphData.fromJson(response.data);
  }
}
