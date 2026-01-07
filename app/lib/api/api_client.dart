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
  }) async {
    final response = await _dio.get(
      '/items',
      queryParameters: {
        'page': page,
        'page_size': pageSize,
        if (topicId != null) 'topic_id': topicId,
        if (search != null && search.isNotEmpty) 'search': search,
      },
    );
    return PaginatedItems.fromJson(response.data);
  }

  Future<ContentItem> getItem(int id) async {
    final response = await _dio.get('/items/$id');
    return ContentItem.fromJson(response.data);
  }

  Future<void> deleteItem(int id) async {
    await _dio.delete('/items/$id');
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
}
