import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/utils/notification_routes.dart';

void main() {
  group('notificationRoute', () {
    test('an integer item id maps to the item detail route', () {
      expect(notificationRoute('42'), '/item/42');
    });

    test('a weekly payload maps to the weekly screen', () {
      expect(notificationRoute('weekly:7'), '/weekly');
    });

    test('null / empty map to no route', () {
      expect(notificationRoute(null), isNull);
      expect(notificationRoute(''), isNull);
    });

    test('an unrecognised payload maps to no route', () {
      expect(notificationRoute('garbage'), isNull);
    });
  });
}
