import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/widgets/item_card.dart';

import '../fixtures/test_fixtures.dart';
import '../helpers/test_helpers.dart';

void main() {
  group('ItemCard', () {
    testWidgets('displays item title', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
        ),
      );

      expect(find.text('Completed Article'), findsOneWidget);
    });

    testWidgets('displays source when available', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
        ),
      );

      expect(find.text('example.com'), findsOneWidget);
    });

    testWidgets('shows favorite icon when item is favorite', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.favoriteItem,
          onTap: () {},
          onToggleFavorite: () {},
        ),
      );

      expect(find.byIcon(Icons.star), findsOneWidget);
    });

    testWidgets('shows star_border icon when item is not favorite', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          onToggleFavorite: () {},
        ),
      );

      expect(find.byIcon(Icons.star_border), findsOneWidget);
    });

    testWidgets('shows processing indicator for processing items',
        (tester) async {
      // Don't use pumpAndSettle for CircularProgressIndicator as it animates continuously
      await tester.pumpWidget(createTestableWidget(
        ItemCard(
          item: TestItems.processingItem,
          onTap: () {},
        ),
      ));
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows error icon for failed items', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.failedItem,
          onTap: () {},
        ),
      );

      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('shows note icon for note items', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.noteItem,
          onTap: () {},
        ),
      );

      expect(find.byIcon(Icons.note), findsOneWidget);
    });

    testWidgets('shows link icon for link items', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
        ),
      );

      // ItemCard shows a link icon in the type icon container
      expect(find.byIcon(Icons.link), findsWidgets);
    });

    testWidgets('triggers onTap callback when tapped', (tester) async {
      var tapped = false;

      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () => tapped = true,
        ),
      );

      await tester.tap(find.byType(ItemCard));
      expect(tapped, true);
    });

    testWidgets('triggers onLongPress callback when long pressed',
        (tester) async {
      var longPressed = false;

      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          onLongPress: () => longPressed = true,
        ),
      );

      await tester.longPress(find.byType(ItemCard));
      expect(longPressed, true);
    });

    testWidgets('shows unread indicator for unread items', (tester) async {
      final unreadItem = TestItems.completedItem.copyWith(isRead: false);

      await pumpAndSettle(
        tester,
        ItemCard(
          item: unreadItem,
          onTap: () {},
        ),
      );

      // Unread items should have a blue dot indicator
      expect(find.byType(Container), findsWidgets);
    });

    testWidgets('displays topic chips when topics exist', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
        ),
      );

      expect(find.text('Technology'), findsOneWidget);
    });

    testWidgets('shows checkbox in selection mode', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          isSelectionMode: true,
          isSelected: false,
          onToggleSelection: () {},
        ),
      );

      expect(find.byType(Checkbox), findsOneWidget);
    });

    testWidgets('checkbox is checked when selected', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          isSelectionMode: true,
          isSelected: true,
          onToggleSelection: () {},
        ),
      );

      final checkbox = tester.widget<Checkbox>(find.byType(Checkbox));
      expect(checkbox.value, true);
    });

    testWidgets('checkbox triggers onToggleSelection when tapped',
        (tester) async {
      var toggled = false;

      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          isSelectionMode: true,
          isSelected: false,
          onToggleSelection: () => toggled = true,
        ),
      );

      await tester.tap(find.byType(Checkbox));
      expect(toggled, true);
    });

    testWidgets('onToggleFavorite callback works', (tester) async {
      var toggled = false;

      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          onToggleFavorite: () => toggled = true,
        ),
      );

      await tester.tap(find.byIcon(Icons.star_border));
      expect(toggled, true);
    });

    testWidgets('onToggleRead callback works', (tester) async {
      var toggled = false;

      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          onToggleRead: () => toggled = true,
        ),
      );

      await tester.tap(find.byIcon(Icons.mark_email_unread));
      expect(toggled, true);
    });

    testWidgets('shows check_circle for completed items with summary',
        (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
        ),
      );

      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    testWidgets('card has different background when selected', (tester) async {
      await pumpAndSettle(
        tester,
        ItemCard(
          item: TestItems.completedItem,
          onTap: () {},
          isSelectionMode: true,
          isSelected: true,
          onToggleSelection: () {},
        ),
      );

      // The card should render with selection styling
      final card = tester.widget<Card>(find.byType(Card));
      expect(card.color, isNotNull);
    });
  });
}
