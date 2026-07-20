// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'VibedInsight';

  @override
  String get inboxTitle => 'Inbox';

  @override
  String get emptyInboxTitle => 'No items yet';

  @override
  String get emptyInboxSubtitle => 'Add your first URL to get started';

  @override
  String get retry => 'Retry';

  @override
  String get add => 'Add';

  @override
  String get openSettings => 'Open settings';

  @override
  String get chatTitle => 'Ask your archive';

  @override
  String get chatHint => 'Ask a question…';

  @override
  String get chatEmptySubtitle =>
      'Ask a question and I\'ll answer from your saved content.';

  @override
  String get chatSources => 'Sources';

  @override
  String get resurfacedTitle => 'Rediscovered';
}
