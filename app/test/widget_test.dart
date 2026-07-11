import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:vibedinsight/config/app_settings.dart';
import 'package:vibedinsight/main.dart';
import 'package:vibedinsight/providers/api_provider.dart';

void main() {
  testWidgets('App starts and shows inbox', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appSettingsProvider.overrideWith(
            (ref) => AppSettings(serverUrl: 'http://test.local', apiKey: ''),
          ),
        ],
        child: const VibedInsightApp(),
      ),
    );

    // App should show the inbox title
    expect(find.text('Inbox'), findsOneWidget);

    // Let pending network/poll timers (Dio timeout, item polling) elapse so
    // the test binding doesn't fail on pending timers at teardown
    await tester.pump(const Duration(seconds: 40));
  });
}
