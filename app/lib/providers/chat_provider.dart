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
  });

  final bool isUser;
  final String text;
  final List<ChatSource> sources;
  final bool isError;
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

    state = state.copyWith(
      messages: [...state.messages, ChatMessage(isUser: true, text: trimmed)],
      isSending: true,
    );

    try {
      final answer = await _api.chat(trimmed);
      state = state.copyWith(
        messages: [
          ...state.messages,
          ChatMessage(
            isUser: false,
            text: answer.answer,
            sources: answer.sources,
          ),
        ],
        isSending: false,
      );
    } catch (e) {
      state = state.copyWith(
        messages: [
          ...state.messages,
          ChatMessage(
            isUser: false,
            text: describeError(e.toString()).message,
            isError: true,
          ),
        ],
        isSending: false,
      );
    }
  }

  void clear() => state = const ChatState();
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.watch(apiClientProvider));
});
