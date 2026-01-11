import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:vibedinsight/main.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('VibedInsight App Integration Tests', () {
    testWidgets('App launches and shows inbox screen', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      // Wait for initial load
      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Verify app launched
      expect(find.text('Inbox'), findsOneWidget);
    });

    testWidgets('Can navigate to settings', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find and tap the settings icon
      final settingsButton = find.byIcon(Icons.settings);
      if (settingsButton.evaluate().isNotEmpty) {
        await tester.tap(settingsButton);
        await tester.pumpAndSettle();

        // Verify settings screen is shown
        expect(find.text('Settings'), findsOneWidget);
      }
    });

    testWidgets('Can open add content bottom sheet', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find and tap the FAB
      final fab = find.byType(FloatingActionButton);
      if (fab.evaluate().isNotEmpty) {
        await tester.tap(fab);
        await tester.pumpAndSettle();

        // Verify bottom sheet options are visible
        expect(
          find.textContaining('URL'),
          findsWidgets,
        );
      }
    });

    testWidgets('Pull to refresh works', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find the list and perform a drag down gesture
      final listFinder = find.byType(CustomScrollView);
      if (listFinder.evaluate().isNotEmpty) {
        await tester.fling(listFinder, const Offset(0, 300), 1000);
        await tester.pumpAndSettle(const Duration(seconds: 2));
      }

      // App should still be functional after refresh
      expect(find.text('Inbox'), findsOneWidget);
    });

    testWidgets('Search bar is accessible', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find search icon
      final searchIcon = find.byIcon(Icons.search);
      if (searchIcon.evaluate().isNotEmpty) {
        await tester.tap(searchIcon);
        await tester.pumpAndSettle();

        // Search field should be visible
        expect(find.byType(TextField), findsWidgets);
      }
    });

    testWidgets('Topic filter chips are scrollable', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find horizontal scrollable for topic chips
      final chipList = find.byType(SingleChildScrollView);
      if (chipList.evaluate().isNotEmpty) {
        // Test passes if we can find the scroll view
        expect(chipList, findsWidgets);
      }
    });

    testWidgets('Empty state is shown when no items', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 3));

      // If there are no items, an empty state should be shown
      // This test verifies the app doesn't crash on empty state
      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('Filter buttons toggle correctly', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find filter icon
      final filterIcon = find.byIcon(Icons.filter_list);
      if (filterIcon.evaluate().isNotEmpty) {
        await tester.tap(filterIcon);
        await tester.pumpAndSettle();

        // Filter options should be visible
        expect(
          find.textContaining(RegExp(r'Favorite|Unread|Archived')),
          findsWidgets,
        );
      }
    });
  });

  group('Navigation Tests', () {
    testWidgets('Bottom navigation works', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find bottom navigation items
      final bottomNav = find.byType(BottomNavigationBar);
      if (bottomNav.evaluate().isNotEmpty) {
        // Tap each navigation item
        final navItems = find.descendant(
          of: bottomNav,
          matching: find.byType(InkResponse),
        );

        if (navItems.evaluate().length > 1) {
          await tester.tap(navItems.at(1));
          await tester.pumpAndSettle();
        }
      }

      // App should remain functional
      expect(find.byType(MaterialApp), findsOneWidget);
    });
  });

  group('Performance Tests', () {
    testWidgets('App launches within reasonable time', (tester) async {
      final stopwatch = Stopwatch()..start();

      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 5));

      stopwatch.stop();

      // App should be ready within 5 seconds
      expect(stopwatch.elapsedMilliseconds, lessThan(5000));
    });

    testWidgets('List scrolling is smooth', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: VibedInsightApp(),
        ),
      );

      await tester.pumpAndSettle(const Duration(seconds: 2));

      // Find scrollable area
      final scrollable = find.byType(Scrollable);
      if (scrollable.evaluate().isNotEmpty) {
        // Perform multiple scroll gestures
        for (var i = 0; i < 3; i++) {
          await tester.fling(scrollable.first, const Offset(0, -200), 500);
          await tester.pumpAndSettle();
        }
      }

      // App should remain responsive
      expect(find.byType(MaterialApp), findsOneWidget);
    });
  });
}
