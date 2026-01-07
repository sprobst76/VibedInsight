import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:vibedinsight/main.dart';

void main() {
  testWidgets('App starts and shows inbox', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: VibedInsightApp(),
      ),
    );

    // App should show the inbox title
    expect(find.text('Inbox'), findsOneWidget);
  });
}
