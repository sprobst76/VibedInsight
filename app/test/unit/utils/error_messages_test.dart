import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/utils/error_messages.dart';

void main() {
  group('describeError', () {
    test('401 is treated as an auth error', () {
      final info = describeError(
        'DioException [bad response]: status code of 401',
      );
      expect(info.isAuthError, true);
      expect(info.message, contains('API-Key'));
    });

    test('403 is treated as an auth error', () {
      expect(describeError('status code of 403').isAuthError, true);
    });

    test('"Invalid or missing API key" body is an auth error', () {
      final info = describeError('Exception: Invalid or missing API key');
      expect(info.isAuthError, true);
    });

    test('connection errors are network messages, not auth', () {
      for (final raw in [
        'DioException [connectionError]',
        'SocketException: Failed host lookup',
        'DioException: connection timeout',
      ]) {
        final info = describeError(raw);
        expect(info.isAuthError, false, reason: raw);
        expect(info.message, contains('Verbindung'), reason: raw);
      }
    });

    test('404 hints at the server URL', () {
      final info = describeError('status code of 404');
      expect(info.isAuthError, false);
      expect(info.message, contains('URL'));
    });

    test('5xx is reported as a server error', () {
      for (final code in ['500', '502', '503', '504']) {
        final info = describeError('status code of $code');
        expect(info.isAuthError, false, reason: code);
        expect(info.message.toLowerCase(), contains('server'), reason: code);
      }
    });

    test('unknown errors fall back to the raw text', () {
      final info = describeError('some totally unexpected failure');
      expect(info.isAuthError, false);
      expect(info.message, contains('some totally unexpected failure'));
    });
  });
}
