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
  String get shareSavingTitle => 'Wird in VibedInsight gespeichert';

  @override
  String get shareSavedTitle => 'Gespeichert - wird verarbeitet';

  @override
  String get shareQueuedTitle => 'Wartet auf Netz';

  @override
  String shareQueuedBody(String target) {
    return 'Wird später gesendet: $target';
  }

  @override
  String get shareRejectedTitle => 'Konnte nicht hinzugefügt werden';

  @override
  String get shareFailedTitle => 'Speichern fehlgeschlagen';

  @override
  String shareFailedBody(String target) {
    return 'Konnte nicht gespeichert werden: $target';
  }

  @override
  String get shareNoteTitleFallback => 'Geteilte Notiz';

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

  @override
  String get chatTitle => 'Frag dein Archiv';

  @override
  String get chatHint => 'Frag etwas…';

  @override
  String get chatEmptySubtitle =>
      'Stell eine Frage — ich antworte aus deinen gespeicherten Inhalten.';

  @override
  String get chatSources => 'Quellen';

  @override
  String get resurfacedTitle => 'Wiederentdeckt';

  @override
  String get itemFailedTitle => 'Verarbeitung fehlgeschlagen';

  @override
  String itemFailedAttempts(int count) {
    return 'Versuche: $count';
  }

  @override
  String itemRetryError(String error) {
    return 'Erneuter Versuch fehlgeschlagen: $error';
  }

  @override
  String get itemRetryStarted => 'Erneut eingereiht';
}
