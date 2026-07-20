import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vibedinsight/models/chat.dart';
import 'package:vibedinsight/providers/api_provider.dart';
import 'package:vibedinsight/providers/chat_provider.dart';

import '../../mocks/mock_api_client.dart';

void main() {
  late MockApiClient mockApi;

  ProviderContainer makeContainer() {
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(mockApi)],
    );
    addTearDown(container.dispose);
    return container;
  }

  setUp(() => mockApi = MockApiClient());

  test('send appends the question and the answer with sources', () async {
    mockApi.chatAnswerToReturn = const ChatAnswer(
      answer: 'async/await erlaubt Nebenläufigkeit [1].',
      sources: [
        ChatSource(n: 1, id: '8', title: 'Async', similarity: 0.9),
      ],
      usedContext: true,
    );
    final container = makeContainer();

    await container.read(chatProvider.notifier).send('Wie funktioniert async?');

    final state = container.read(chatProvider);
    expect(state.isSending, false);
    expect(state.messages.length, 2);
    expect(state.messages[0].isUser, true);
    expect(state.messages[0].text, 'Wie funktioniert async?');
    expect(state.messages[1].isUser, false);
    expect(state.messages[1].sources.single.id, '8');
    expect(state.messages[1].isStreaming, false);
    expect(mockApi.methodCalls, contains('chatStream'));
  });

  test('streamed deltas accumulate into the answer text', () async {
    mockApi.chatStreamEventsToReturn = [
      {
        'type': 'sources',
        'used_context': true,
        'sources': [
          {'n': 1, 'id': '5', 'title': 'Quelle', 'similarity': 0.8},
        ],
      },
      {'type': 'delta', 'text': 'Hallo '},
      {'type': 'delta', 'text': 'Welt'},
      {'type': 'done'},
    ];
    final container = makeContainer();

    await container.read(chatProvider.notifier).send('Frage');

    final msg = container.read(chatProvider).messages.last;
    expect(msg.isUser, false);
    expect(msg.text, 'Hallo Welt');
    expect(msg.sources.single.id, '5');
    expect(msg.isStreaming, false);
  });

  test('a stream error event marks the message as an error', () async {
    mockApi.chatStreamEventsToReturn = [
      {'type': 'error', 'message': 'boom'},
    ];
    final container = makeContainer();

    await container.read(chatProvider.notifier).send('Frage');

    final msg = container.read(chatProvider).messages.last;
    expect(msg.isError, true);
    expect(msg.isStreaming, false);
  });

  test('a failed request yields an error assistant message', () async {
    mockApi.setFailure('boom');
    final container = makeContainer();

    await container.read(chatProvider.notifier).send('Frage');

    final state = container.read(chatProvider);
    expect(state.isSending, false);
    expect(state.messages.length, 2);
    expect(state.messages[1].isError, true);
    expect(state.messages[1].isUser, false);
  });

  test('blank input is ignored', () async {
    final container = makeContainer();
    await container.read(chatProvider.notifier).send('   ');
    expect(container.read(chatProvider).messages, isEmpty);
    expect(mockApi.methodCalls, isNot(contains('chatStream')));
  });

  test('clear resets the conversation', () async {
    final container = makeContainer();
    await container.read(chatProvider.notifier).send('Frage');
    expect(container.read(chatProvider).messages, isNotEmpty);

    container.read(chatProvider.notifier).clear();
    expect(container.read(chatProvider).messages, isEmpty);
  });
}
