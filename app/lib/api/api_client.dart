import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import '../config/api_config.dart';
import '../models/chat.dart';
import '../models/content_item.dart';

class ApiClient {
  late final Dio _dio;

  ApiClient({required String baseUrl, String apiKey = ''}) {
    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: ApiConfig.connectTimeout,
        receiveTimeout: ApiConfig.receiveTimeout,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (apiKey.isNotEmpty) 'X-API-Key': apiKey,
        },
      ),
    );

    // Log requests in debug builds only (bodies may contain personal data)
    if (kDebugMode) {
      _dio.interceptors.add(
        LogInterceptor(
          requestBody: true,
          responseBody: true,
          error: true,
        ),
      );
    }
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

  /// Verify the API key against a protected endpoint.
  ///
  /// `/health` is public, so it succeeds even with a wrong key — this hits a
  /// key-protected endpoint so the settings screen can tell a reachable server
  /// with an invalid key apart from a working connection.
  /// Returns true on 200, false on 401/403; other errors propagate.
  Future<bool> checkAuth() async {
    try {
      final response = await _dio.get(
        '/items',
        queryParameters: {'page': 1, 'page_size': 1},
      );
      return response.statusCode == 200;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      if (code == 401 || code == 403) return false;
      rethrow;
    }
  }

  // Items
  Future<PaginatedItems> getItems({
    int page = 1,
    int pageSize = ApiConfig.pageSize,
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

  Future<ContentItem> setRating(int id, int rating) async {
    final response = await _dio.post(
      '/items/$id/rating',
      data: {'rating': rating},
    );
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

  // Chat / RAG — "Frag dein Archiv"
  Future<ChatAnswer> chat(String question, {int? topK}) async {
    final response = await _dio.post(
      '/chat',
      data: {
        'question': question,
        if (topK != null) 'top_k': topK,
      },
      // The archive query hits Ollama; allow it more time than the default.
      options: Options(receiveTimeout: const Duration(seconds: 180)),
    );
    return ChatAnswer.fromJson(response.data as Map<String, dynamic>);
  }

  /// Streamed chat: yields NDJSON events (`sources`, `delta`, `answer`,
  /// `error`, `done`) as they arrive, so the UI can show sources instantly and
  /// stream the answer token by token.
  Stream<Map<String, dynamic>> chatStream(String question, {int? topK}) async* {
    final response = await _dio.post<ResponseBody>(
      '/chat/stream',
      data: {
        'question': question,
        if (topK != null) 'top_k': topK,
      },
      options: Options(
        responseType: ResponseType.stream,
        receiveTimeout: const Duration(seconds: 200),
      ),
    );

    // Buffer bytes and split on newline (0x0A) — a newline byte never occurs
    // inside a UTF-8 multibyte sequence, so each complete line decodes cleanly.
    final bytes = <int>[];
    await for (final chunk in response.data!.stream) {
      bytes.addAll(chunk);
      int nl;
      while ((nl = bytes.indexOf(10)) >= 0) {
        final line = utf8.decode(bytes.sublist(0, nl)).trim();
        bytes.removeRange(0, nl + 1);
        if (line.isNotEmpty) yield jsonDecode(line) as Map<String, dynamic>;
      }
    }
    final rest = utf8.decode(bytes).trim();
    if (rest.isNotEmpty) yield jsonDecode(rest) as Map<String, dynamic>;
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
    final response = await _dio.post('/items/$id/reprocess');
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

  Future<WeeklySummary> generateWeeklySummary(int id, {int? topicId}) async {
    final response = await _dio.post(
      '/weekly/$id/generate',
      queryParameters: topicId != null ? {'topic_id': topicId} : null,
    );
    return WeeklySummary.fromJson(response.data);
  }

  Future<WeeklySummary> generateCurrentWeekSummary({int? topicId}) async {
    final response = await _dio.post(
      '/weekly/generate-current',
      queryParameters: topicId != null ? {'topic_id': topicId} : null,
    );
    return WeeklySummary.fromJson(response.data);
  }

  Future<String> downloadExport() async {
    final dir = await getApplicationDocumentsDirectory();
    final date = DateTime.now().toIso8601String().substring(0, 10);
    final savePath = '${dir.path}/vibedinsight-export-$date.zip';
    await _dio.download('/export/markdown', savePath);
    return savePath;
  }

  // Graph Data
  Future<GraphData> getGraphData() async {
    final response = await _dio.get('/items/graph/data');
    return GraphData.fromJson(response.data);
  }
}
