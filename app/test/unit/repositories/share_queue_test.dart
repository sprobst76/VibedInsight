import 'dart:async';

import 'package:dio/dio.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/api/api_client.dart';
import 'package:vibedinsight/database/app_database.dart';
import 'package:vibedinsight/models/content_item.dart';
import 'package:vibedinsight/repositories/items_repository.dart';
import 'package:vibedinsight/services/share_ingest.dart';

import '../../fixtures/test_fixtures.dart';
import '../../helpers/sqlite_test_setup.dart';
import '../../mocks/mock_api_client.dart';

/// Mock whose ingest calls can fail with a chosen error or hang.
class _FakeApi extends MockApiClient {
  Object? error;
  bool hang = false;

  Future<T> _run<T>(T value) async {
    if (hang) return Completer<T>().future;
    if (error != null) throw error!;
    return value;
  }

  @override
  Future<ContentItem> ingestUrl(String url) {
    methodCalls.add('ingestUrl');
    lastCallParams['url'] = url;
    return _run(TestItems.pendingItem);
  }

  @override
  Future<ContentItem> ingestText({
    required String title,
    required String text,
    String contentType = 'note',
  }) {
    methodCalls.add('ingestText');
    lastCallParams.addAll({'title': title, 'text': text});
    return _run(TestItems.noteItem);
  }
}

DioException _http(int code) => DioException(
      requestOptions: RequestOptions(path: '/x'),
      response: Response(
          requestOptions: RequestOptions(path: '/x'), statusCode: code),
      type: DioExceptionType.badResponse,
    );

DioException _net() => DioException(
      requestOptions: RequestOptions(path: '/x'),
      type: DioExceptionType.connectionError,
    );

void main() {
  late _FakeApi api;
  late AppDatabase db;
  late ItemsRepository repo;

  setUp(() {
    useSystemSqlite();
    api = _FakeApi();
    db = AppDatabase(NativeDatabase.memory());
    repo = ItemsRepository(api, db);
  });

  tearDown(() async {
    repo.dispose();
    await db.close();
  });

  const short = Duration(milliseconds: 50);

  group('share ingest', () {
    test('success does not queue', () async {
      final o = await ingestSharedUrl(repo, 'https://a.test/x', timeout: short);
      expect(o.kind, ShareOutcomeKind.saved);
      expect(await db.getPendingActions(), isEmpty);
    });

    test('network error queues exactly one entry', () async {
      api.error = _net();
      final o = await ingestSharedUrl(repo, 'https://a.test/x', timeout: short);
      expect(o.kind, ShareOutcomeKind.queued);
      final q = await db.getPendingActions();
      expect(q, hasLength(1));
      expect(q.single.actionType, 'ingest_url');
    });

    test('timeout queues', () async {
      api.hang = true;
      final o = await ingestSharedUrl(repo, 'https://a.test/x', timeout: short);
      expect(o.kind, ShareOutcomeKind.queued);
      expect(await db.getPendingActions(), hasLength(1));
    });

    test('400 is rejected with detail and not queued', () async {
      api.error = IngestRejectedException('private URL');
      final o = await ingestSharedUrl(repo, 'http://10.0.0.1', timeout: short);
      expect(o.kind, ShareOutcomeKind.rejected);
      expect(o.message, 'private URL');
      expect(await db.getPendingActions(), isEmpty);
    });

    test('text without URL becomes a note with first-line title', () async {
      final o = await ingestSharedNote(repo, '\n  Hello world\nsecond line',
          fallbackTitle: 'Shared note', timeout: short);
      expect(o.kind, ShareOutcomeKind.saved);
      expect(api.methodCalls, contains('ingestText'));
      expect(api.lastCallParams['title'], 'Hello world');
    });

    test('note offline is queued as ingest_note', () async {
      api.error = _net();
      final o = await ingestSharedNote(repo, 'x' * 100,
          fallbackTitle: 'Shared note', timeout: short);
      expect(o.kind, ShareOutcomeKind.queued);
      expect((await db.getPendingActions()).single.actionType, 'ingest_note');
      expect(noteTitleFromText('x' * 100, 'f').length, lessThanOrEqualTo(63));
    });
  });

  group('syncPendingActions', () {
    test('drops 400 entry, keeps network-error entry', () async {
      await db.addPendingAction('ingest_url', payload: {'url': 'https://bad'});
      api.error = _http(400);
      await repo.syncPendingActions();
      expect(await db.getPendingActions(), isEmpty);

      await db.addPendingAction('ingest_url', payload: {'url': 'https://ok'});
      api.error = _net();
      final r = await repo.syncPendingActions();
      expect(r.failed, 1);
      final q = await db.getPendingActions();
      expect(q, hasLength(1));
      expect(q.single.retryCount, 0);
    });

    test('IngestRejectedException drops the entry', () async {
      await db.addPendingAction('ingest_url', payload: {'url': 'http://10.0.0.1'});
      api.error = IngestRejectedException('private');
      await repo.syncPendingActions();
      expect(await db.getPendingActions(), isEmpty);
    });

    test('gives up after max retries on server errors', () async {
      await db.addPendingAction('ingest_url', payload: {'url': 'https://x'});
      api.error = _http(500);
      for (var i = 0; i < ItemsRepository.maxPendingRetries - 1; i++) {
        await repo.syncPendingActions();
        expect(await db.getPendingActions(), hasLength(1));
      }
      await repo.syncPendingActions();
      expect(await db.getPendingActions(), isEmpty);
    });

    test('success removes entry', () async {
      await db.addPendingAction('ingest_url', payload: {'url': 'https://x'});
      final r = await repo.syncPendingActions();
      expect(r.synced, 1);
      expect(await db.getPendingActions(), isEmpty);
    });
  });
}
