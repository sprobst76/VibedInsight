enum ContentType {
  link,
  newsletter,
  pdf,
  note;

  static ContentType fromString(String value) {
    return ContentType.values.firstWhere(
      (e) => e.name == value,
      orElse: () => ContentType.link,
    );
  }
}

enum ProcessingStatus {
  pending,
  processing,
  completed,
  failed;

  static ProcessingStatus fromString(String value) {
    return ProcessingStatus.values.firstWhere(
      (e) => e.name == value,
      orElse: () => ProcessingStatus.pending,
    );
  }
}

class Topic {
  final int id;
  final String name;
  final DateTime createdAt;

  Topic({
    required this.id,
    required this.name,
    required this.createdAt,
  });

  factory Topic.fromJson(Map<String, dynamic> json) {
    return Topic(
      id: json['id'] as int,
      name: json['name'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

class ContentItem {
  final int id;
  final ContentType contentType;
  final ProcessingStatus status;
  final String? url;
  final String? title;
  final String? source;
  final String? rawText;
  final String? summary;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final DateTime? processedAt;
  final List<Topic> topics;

  ContentItem({
    required this.id,
    required this.contentType,
    required this.status,
    this.url,
    this.title,
    this.source,
    this.rawText,
    this.summary,
    required this.createdAt,
    this.updatedAt,
    this.processedAt,
    this.topics = const [],
  });

  factory ContentItem.fromJson(Map<String, dynamic> json) {
    return ContentItem(
      id: json['id'] as int,
      contentType: ContentType.fromString(json['content_type'] as String),
      status: ProcessingStatus.fromString(json['status'] as String),
      url: json['url'] as String?,
      title: json['title'] as String?,
      source: json['source'] as String?,
      rawText: json['raw_text'] as String?,
      summary: json['summary'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'] as String)
          : null,
      processedAt: json['processed_at'] != null
          ? DateTime.parse(json['processed_at'] as String)
          : null,
      topics: (json['topics'] as List<dynamic>?)
              ?.map((e) => Topic.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  String get displayTitle => title ?? url ?? 'Untitled';

  bool get isProcessing => status == ProcessingStatus.processing;
  bool get isCompleted => status == ProcessingStatus.completed;
  bool get hasSummary => summary != null && summary!.isNotEmpty;
}

enum RelationType {
  related,
  extends_,
  contradicts,
  similar,
  references;

  static RelationType fromString(String value) {
    if (value == 'extends') return RelationType.extends_;
    return RelationType.values.firstWhere(
      (e) => e.name == value || e.name == '${value}_',
      orElse: () => RelationType.related,
    );
  }

  String get displayName {
    switch (this) {
      case RelationType.related:
        return 'Related';
      case RelationType.extends_:
        return 'Extends';
      case RelationType.contradicts:
        return 'Contradicts';
      case RelationType.similar:
        return 'Similar';
      case RelationType.references:
        return 'References';
    }
  }
}

class RelatedItem {
  final int id;
  final String? title;
  final String? source;
  final RelationType relationType;
  final double confidence;

  RelatedItem({
    required this.id,
    this.title,
    this.source,
    required this.relationType,
    required this.confidence,
  });

  factory RelatedItem.fromJson(Map<String, dynamic> json) {
    return RelatedItem(
      id: json['id'] as int,
      title: json['title'] as String?,
      source: json['source'] as String?,
      relationType: RelationType.fromString(json['relation_type'] as String),
      confidence: (json['confidence'] as num).toDouble(),
    );
  }

  String get displayTitle => title ?? 'Untitled';
}

class ContentItemWithRelations extends ContentItem {
  final List<RelatedItem> relatedItems;

  ContentItemWithRelations({
    required super.id,
    required super.contentType,
    required super.status,
    super.url,
    super.title,
    super.source,
    super.rawText,
    super.summary,
    required super.createdAt,
    super.updatedAt,
    super.processedAt,
    super.topics,
    this.relatedItems = const [],
  });

  factory ContentItemWithRelations.fromJson(Map<String, dynamic> json) {
    return ContentItemWithRelations(
      id: json['id'] as int,
      contentType: ContentType.fromString(json['content_type'] as String),
      status: ProcessingStatus.fromString(json['status'] as String),
      url: json['url'] as String?,
      title: json['title'] as String?,
      source: json['source'] as String?,
      rawText: json['raw_text'] as String?,
      summary: json['summary'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'] as String)
          : null,
      processedAt: json['processed_at'] != null
          ? DateTime.parse(json['processed_at'] as String)
          : null,
      topics: (json['topics'] as List<dynamic>?)
              ?.map((e) => Topic.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      relatedItems: (json['related_items'] as List<dynamic>?)
              ?.map((e) => RelatedItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  bool get hasRelatedItems => relatedItems.isNotEmpty;
}

class PaginatedItems {
  final List<ContentItem> items;
  final int total;
  final int page;
  final int pageSize;
  final int pages;

  PaginatedItems({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.pages,
  });

  factory PaginatedItems.fromJson(Map<String, dynamic> json) {
    return PaginatedItems(
      items: (json['items'] as List<dynamic>)
          .map((e) => ContentItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      page: json['page'] as int,
      pageSize: json['page_size'] as int,
      pages: json['pages'] as int,
    );
  }
}
