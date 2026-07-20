// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for German (`de`).
class AppLocalizationsDe extends AppLocalizations {
  AppLocalizationsDe([String locale = 'de']) : super(locale);

  @override
  String get appTitle => 'VibedInsight';

  @override
  String get inboxTitle => 'Posteingang';

  @override
  String get emptyInboxTitle => 'Noch keine Einträge';

  @override
  String get emptyInboxSubtitle => 'Füge deine erste URL hinzu, um zu starten';

  @override
  String get retry => 'Erneut versuchen';

  @override
  String get add => 'Hinzufügen';

  @override
  String get openSettings => 'Einstellungen öffnen';
}
