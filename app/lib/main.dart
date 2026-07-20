import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:timeago/timeago.dart' as timeago;

import 'l10n/app_localizations.dart';
import 'config/app_settings.dart';
import 'screens/inbox_screen.dart';
import 'screens/detail_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/weekly_screen.dart';
import 'screens/graph_screen.dart';
import 'services/notification_service.dart';
import 'providers/api_provider.dart';
import 'providers/share_intent_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize notifications
  await NotificationService().initialize();

  // Initialize date formatting for German locale
  await initializeDateFormatting('de_DE');

  // Initialize timeago localization
  timeago.setLocaleMessages('de', timeago.DeMessages());

  // Load persisted connection settings (server URL + API key)
  final settings = await AppSettings.load();

  runApp(
    ProviderScope(
      overrides: [
        appSettingsProvider.overrideWith((ref) => settings),
      ],
      child: const VibedInsightApp(),
    ),
  );
}

/// The app router. Public so widget/integration tests can reset it to '/'
/// between pumps (it is a top-level singleton and otherwise keeps its
/// location across test cases).
final appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const InboxScreen(),
    ),
    GoRoute(
      path: '/item/:id',
      builder: (context, state) {
        final id = int.parse(state.pathParameters['id']!);
        return DetailScreen(itemId: id);
      },
    ),
    GoRoute(
      path: '/weekly',
      builder: (context, state) => const WeeklyScreen(),
    ),
    GoRoute(
      path: '/graph',
      builder: (context, state) => const GraphScreen(),
    ),
    GoRoute(
      path: '/settings',
      builder: (context, state) => const SettingsScreen(),
    ),
  ],
);

class VibedInsightApp extends ConsumerWidget {
  const VibedInsightApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Initialize share intent provider immediately on app start
    // This ensures we catch share intents even before any screen loads
    ref.read(shareIntentProvider);

    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      debugShowCheckedModeBanner: false,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: _buildLightTheme(),
      darkTheme: _buildDarkTheme(),
      themeMode: ThemeMode.system,
      routerConfig: appRouter,
    );
  }

  ThemeData _buildLightTheme() {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: Colors.indigo,
        brightness: Brightness.light,
      ),
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: Colors.grey.shade200,
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }

  ThemeData _buildDarkTheme() {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: Colors.indigo,
        brightness: Brightness.dark,
      ),
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: Colors.grey.shade800,
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }
}
