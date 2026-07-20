import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/chat.dart';
import '../utils/error_messages.dart';
import 'api_provider.dart';

/// One turn in the chat: either the user's question or the assistant's answer.
class ChatMessage {
  const ChatMessage({
    required this.isUser,
    required this.text,
    this.sources = const [],
    this.isError = false,
    this.isStreaming = false,
  });

  final bool isUser;
  final String text;
  final List<ChatSource> sources;
  final bool isError;

  /// True while the assistant answer is still streaming in.
  final bool isStreaming;

  ChatMessage copyWith({
    String? text,
    List<ChatSource>? sources,
    bool? isError,
    bool? isStreaming,
  }) {
    return ChatMessage(
      isUser: isUser,
      text: text ?? this.text,
      sources: sources ?? this.sources,
      isError: isError ?? this.isError,
      isStreaming: isStreaming ?? this.isStreaming,
    );
  }
}

class ChatState {
  const ChatState({this.messages = const [], this.isSending = false});

  final List<ChatMessage> messages;
  final bool isSending;

  ChatState copyWith({List<ChatMessage>? messages, bool? isSending}) {
    return ChatState(
      messages: messages ?? this.messages,
      isSending: isSending ?? this.isSending,
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  ChatNotifier(this._api) : super(const ChatState());

  final ApiClient _api;

  Future<void> send(String question) async {
    final trimmed = question.trim();
    if (trimmed.isEmpty || state.isSending) return;

    // Append the question and an empty, streaming assistant placeholder.
    state = state.copyWith(
      messages: [
        ...state.messages,
        ChatMessage(isUser: true, text: trimmed),
        const ChatMessage(isUser: false, text: '', isStreaming: true),
      ],
      isSending: true,
    );

    final buffer = StringBuffer();
    try {
      await for (final event in _api.chatStream(trimmed)) {
        switch (event['type']) {
          case 'sources':
            _updateAssistant(sources: _parseSources(event['sources']));
          case 'answer': // no-context path: a single complete answer
            buffer.write(event['answer'] ?? '');
            _updateAssistant(text: buffer.toString());
          case 'delta':
            buffer.write(event['text'] ?? '');
            _updateAssistant(text: buffer.toString());
          case 'error':
            _updateAssistant(
              text: describeError('${event['message']}').message,
              isError: true,
            );
        }
      }
    } catch (e) {
      _updateAssistant(text: describeError(e.toString()).message, isError: true);
    } finally {
      _updateAssistant(isStreaming: false);
      state = state.copyWith(isSending: false);
    }
  }

  /// Replace the last (assistant) message with an updated copy.
  void _updateAssistant({
    String? text,
    List<ChatSource>? sources,
    bool? isError,
    bool? isStreaming,
  }) {
    if (state.messages.isEmpty) return;
    final messages = [...state.messages];
    messages[messages.length - 1] = messages.last.copyWith(
      text: text,
      sources: sources,
      isError: isError,
      isStreaming: isStreaming,
    );
    state = state.copyWith(messages: messages);
  }

  List<ChatSource> _parseSources(dynamic raw) {
    if (raw is! List) return const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(ChatSource.fromJson)
        .toList();
  }

  void clear() => state = const ChatState();
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.watch(apiClientProvider));
});
