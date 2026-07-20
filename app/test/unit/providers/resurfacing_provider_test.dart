import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vibedinsight/models/content_item.dart';
import 'package:vibedinsight/providers/api_provider.dart';
import 'package:vibedinsight/providers/resurfacing_provider.dart';

import '../../mocks/mock_api_client.dart';

ContentItem _item(int id, {String title = 'Alter Fund'}) => ContentItem(
      id: id,
      contentType: ContentType.link,
      status: ProcessingStatus.completed,
      title: title,
      createdAt: DateTime(2024, 1, 1),
    );

void main() {
  late MockApiClient mockApi;

  setUp(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    // Pretend a notification was already shown today so _maybeNotify short-
    // circuits before touching the (unavailable) notifications plugin.
    final today = DateTime.now().toIso8601String().substring(0, 10);
    SharedPreferences.setMockInitialValues({'resurface_last_shown': today});
    mockApi = MockApiClient();
  });

  ProviderContainer makeContainer() {
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(mockApi)],
    );
    addTearDown(container.dispose);
    return container;
  }

  // Let the notifier's constructor auto-load settle.
  Future<void> settle() =>
      Future<void>.delayed(const Duration(milliseconds: 20));

  test('surfaces the item the API returns (auto-loads on creation)', () async {
    mockApi.resurfacingToReturn = _item(9);
    final container = makeContainer();

    container.read(resurfacingProvider.notifier); // triggers constructor load
    await settle();

    expect(container.read(resurfacingProvider)?.id, 9);
    expect(mockApi.methodCalls, contains('getResurfacing'));
  });

  test('leaves state null when there is nothing to resurface', () async {
    mockApi.resurfacingToReturn = null;
    final container = makeContainer();

    container.read(resurfacingProvider.notifier);
    await settle();

    expect(container.read(resurfacingProvider), isNull);
  });

  test('dismiss clears the surfaced item', () async {
    mockApi.resurfacingToReturn = _item(1);
    final container = makeContainer();
    final notifier = container.read(resurfacingProvider.notifier);
    await settle();
    expect(container.read(resurfacingProvider), isNotNull);

    notifier.dismiss();
    expect(container.read(resurfacingProvider), isNull);
  });

  test('fetches only once per session', () async {
    mockApi.resurfacingToReturn = _item(2);
    final container = makeContainer();
    final notifier = container.read(resurfacingProvider.notifier);
    await settle();

    await notifier.load(); // explicit extra call is a no-op

    final calls =
        mockApi.methodCalls.where((c) => c == 'getResurfacing').length;
    expect(calls, 1);
  });

  test('an API error is swallowed (state stays null)', () async {
    mockApi.setFailure('boom');
    final container = makeContainer();

    container.read(resurfacingProvider.notifier);
    await settle();

    expect(container.read(resurfacingProvider), isNull);
  });
}
