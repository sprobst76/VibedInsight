import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:vibedinsight/config/app_settings.dart';
import 'package:vibedinsight/database/app_database.dart';
import 'package:vibedinsight/main.dart';
import 'package:vibedinsight/providers/api_provider.dart';
import 'package:vibedinsight/widgets/item_card.dart';

import '../test/fixtures/test_fixtures.dart';
import '../test/mocks/mock_api_client.dart';

/// Integration tests that pump the real [VibedInsightApp] against a mock API
/// and an in-memory database, so they run deterministically (no network) and
/// assert on the widgets the app actually builds — a renamed widget or a
/// broken flow now fails the test instead of being silently skipped.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  // Only completed items: pending/processing items make the notifier start a
  // periodic poll timer, which would keep pumpAndSettle from ever settling.
  final completedItems = <dynamic>[
    TestItems.completedItem, // 'Completed Article'
    TestItems.favoriteItem,
    TestItems.readItem,
  ];

  /// Pump the app with hermetic overrides. Returns the mock so tests can
  /// assert on the calls the UI made.
  Future<MockApiClient> pumpApp(
    WidgetTester tester, {
    List<dynamic>? items,
  }) async {
    final mock = MockApiClient()
      ..itemsToReturn = (items ?? completedItems).cast();
    final db = AppDatabase(NativeDatabase.memory());
    addTearDown(() async => db.close());

    // The app router is a top-level singleton that keeps its location across
    // test cases; reset to the inbox so a prior test's navigation doesn't leak.
    appRouter.go('/');

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appSettingsProvider.overrideWith(
            (ref) => AppSettings(
              serverUrl: 'http://test.local',
              apiKey: 'test-key',
            ),
          ),
          apiClientProvider.overrideWithValue(mock),
          appDatabaseProvider.overrideWithValue(db),
        ],
        child: const VibedInsightApp(),
      ),
    );
    // Short settle timeout so an unexpected non-settling tree (e.g. a repeating
    // animation or poll timer) fails fast instead of blocking for 10 minutes.
    await tester.pumpAndSettle(
      const Duration(milliseconds: 100),
      EnginePhase.sendSemanticsUpdate,
      const Duration(seconds: 30),
    );
    return mock;
  }

  group('Inbox', () {
    testWidgets('launches and renders the items from the API', (tester) async {
      final mock = await pumpApp(tester);

      // Locale-independent anchors (the app is localized de/en).
      expect(find.byType(AppBar), findsOneWidget);
      expect(mock.methodCalls, contains('getItems'));
      expect(find.byType(ItemCard), findsNWidgets(completedItems.length));
      expect(find.text('Completed Article'), findsOneWidget); // item title, not localized
    });

    testWidgets('shows the empty state when the API returns nothing',
        (tester) async {
      await pumpApp(tester, items: const []);

      expect(find.byType(ItemCard), findsNothing);
      // Empty-state icon is stable across locales.
      expect(find.byIcon(Icons.inbox_outlined), findsOneWidget);
    });

    testWidgets('FAB opens the add-content sheet with URL and note options',
        (tester) async {
      await pumpApp(tester);

      await tester.tap(find.byType(FloatingActionButton));
      await tester.pumpAndSettle();

      expect(find.text('Add URL'), findsOneWidget);
      expect(find.text('Add Note'), findsOneWidget);
    });

    testWidgets('overflow menu navigates to the settings screen',
        (tester) async {
      await pumpApp(tester);

      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Einstellungen').last);
      await tester.pumpAndSettle();

      // Settings-screen specific field label — renaming the field fails this.
      expect(find.text('Server-URL'), findsOneWidget);
    });

    testWidgets('search icon reveals a search field', (tester) async {
      await pumpApp(tester);

      await tester.tap(find.byIcon(Icons.search));
      await tester.pumpAndSettle();

      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('the Unread filter chip reloads with unread_only applied',
        (tester) async {
      final mock = await pumpApp(tester);

      // The real chips the inbox renders.
      expect(find.widgetWithText(FilterChip, 'All'), findsOneWidget);
      expect(find.widgetWithText(FilterChip, 'Favorites'), findsOneWidget);
      expect(find.widgetWithText(FilterChip, 'Archived'), findsOneWidget);

      final unread = find.widgetWithText(FilterChip, 'Unread');
      expect(unread, findsOneWidget);
      await tester.ensureVisible(unread);
      await tester.tap(unread);
      await tester.pumpAndSettle();

      expect(mock.lastCallParams['unreadOnly'], true);
    });
  });
}
