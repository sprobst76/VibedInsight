import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/l10n/app_localizations.dart';

void main() {
  Future<void> pumpFor(WidgetTester tester, Locale locale) async {
    await tester.pumpWidget(
      MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(
          builder: (context) {
            final l = AppLocalizations.of(context);
            return Scaffold(
              body: Column(
                children: [
                  Text(l.inboxTitle),
                  Text(l.emptyInboxTitle),
                  Text(l.retry),
                ],
              ),
            );
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('German locale renders German strings', (tester) async {
    await pumpFor(tester, const Locale('de'));
    expect(find.text('Posteingang'), findsOneWidget);
    expect(find.text('Noch keine Einträge'), findsOneWidget);
    expect(find.text('Erneut versuchen'), findsOneWidget);
  });

  testWidgets('English locale renders English strings', (tester) async {
    await pumpFor(tester, const Locale('en'));
    expect(find.text('Inbox'), findsOneWidget);
    expect(find.text('No items yet'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });

  test('de and en are both supported locales', () {
    final codes =
        AppLocalizations.supportedLocales.map((l) => l.languageCode).toSet();
    expect(codes.containsAll(['de', 'en']), isTrue);
  });
}
