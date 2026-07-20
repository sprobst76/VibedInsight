// Models for the RAG chat ("Frag dein Archiv") feature.

class ChatSource {
  const ChatSource({
    required this.n,
    required this.id,
    required this.title,
    this.url,
    this.source,
    required this.similarity,
  });

  /// Citation number ([n]) referenced in the answer text.
  final int n;

  /// ContentItem id (UUID string) — used to open the item.
  final String id;
  final String title;
  final String? url;
  final String? source;
  final double similarity;

  factory ChatSource.fromJson(Map<String, dynamic> json) {
    return ChatSource(
      n: json['n'] as int,
      id: json['id'] as String,
      title: json['title'] as String? ?? 'Ohne Titel',
      url: json['url'] as String?,
      source: json['source'] as String?,
      similarity: (json['similarity'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class ChatAnswer {
  const ChatAnswer({
    required this.answer,
    required this.sources,
    required this.usedContext,
  });

  final String answer;
  final List<ChatSource> sources;

  /// False when the archive had nothing relevant (no LLM call was made).
  final bool usedContext;

  factory ChatAnswer.fromJson(Map<String, dynamic> json) {
    return ChatAnswer(
      answer: json['answer'] as String? ?? '',
      sources: (json['sources'] as List<dynamic>? ?? [])
          .map((e) => ChatSource.fromJson(e as Map<String, dynamic>))
          .toList(),
      usedContext: json['used_context'] as bool? ?? false,
    );
  }
}
