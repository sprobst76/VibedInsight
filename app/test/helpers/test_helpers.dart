/// Test helpers and utilities for VibedInsight tests
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Creates a MaterialApp wrapper for widget testing
Widget createTestableWidget(Widget child, {List<Override>? overrides}) {
  return ProviderScope(
    overrides: overrides ?? [],
    child: MaterialApp(
      home: child,
    ),
  );
}

/// Creates a ProviderContainer for unit testing providers
ProviderContainer createContainer({List<Override>? overrides}) {
  final container = ProviderContainer(overrides: overrides ?? []);
  addTearDown(container.dispose);
  return container;
}

/// Pump widget and wait for async operations
Future<void> pumpAndSettle(WidgetTester tester, Widget widget,
    {List<Override>? overrides}) async {
  await tester.pumpWidget(createTestableWidget(widget, overrides: overrides));
  await tester.pumpAndSettle();
}
