/// Maps raw error strings (usually `Exception`/`DioException.toString()`) to
/// friendly, actionable German messages for the UI.
///
/// Kept as a pure function so it can be unit-tested without widgets.
library;

class ErrorInfo {
  const ErrorInfo(this.message, {this.isAuthError = false});

  /// Human-readable, actionable message.
  final String message;

  /// True when the cause is an invalid/missing API key — the UI can then
  /// offer a shortcut into the settings screen.
  final bool isAuthError;
}

/// Translate a raw error string into an [ErrorInfo].
ErrorInfo describeError(String raw) {
  final s = raw.toLowerCase();

  if (s.contains('401') ||
      s.contains('403') ||
      s.contains('invalid or missing api key') ||
      s.contains('api key')) {
    return const ErrorInfo(
      'API-Key ungültig oder fehlt. Bitte in den Einstellungen prüfen.',
      isAuthError: true,
    );
  }

  if (s.contains('connectionerror') ||
      s.contains('socketexception') ||
      s.contains('failed host lookup') ||
      s.contains('connection refused') ||
      s.contains('timeout') ||
      s.contains('timed out')) {
    return const ErrorInfo(
      'Keine Verbindung zum Server. Ist die Server-URL korrekt und der '
      'Server erreichbar?',
    );
  }

  if (s.contains('404')) {
    return const ErrorInfo(
      'Server-Endpunkt nicht gefunden — bitte die Server-URL prüfen.',
    );
  }

  if (s.contains('500') ||
      s.contains('502') ||
      s.contains('503') ||
      s.contains('504')) {
    return const ErrorInfo(
      'Der Server hat einen Fehler gemeldet. Bitte später erneut versuchen.',
    );
  }

  return ErrorInfo('Etwas ist schiefgelaufen: $raw');
}
