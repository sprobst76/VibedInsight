import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/content_item.dart';
import '../services/notification_service.dart';
import 'api_provider.dart';

class WeeklyState {
  final WeeklySummary? currentWeek;
  final List<WeeklySummaryListItem> summaries;
  final bool isLoading;
  final bool isGenerating;
  final String? error;
  final int? selectedTopicId;
  final String? selectedTopicName;

  WeeklyState({
    this.currentWeek,
    this.summaries = const [],
    this.isLoading = false,
    this.isGenerating = false,
    this.error,
    this.selectedTopicId,
    this.selectedTopicName,
  });

  static const _unsetError = Object();

  WeeklyState copyWith({
    WeeklySummary? currentWeek,
    List<WeeklySummaryListItem>? summaries,
    bool? isLoading,
    bool? isGenerating,
    Object? error = _unsetError,
    int? selectedTopicId,
    String? selectedTopicName,
    bool clearTopicFilter = false,
  }) {
    return WeeklyState(
      currentWeek: currentWeek ?? this.currentWeek,
      summaries: summaries ?? this.summaries,
      isLoading: isLoading ?? this.isLoading,
      isGenerating: isGenerating ?? this.isGenerating,
      // Sentinel: omitting `error` keeps the current value; null clears it
      error: identical(error, _unsetError) ? this.error : error as String?,
      selectedTopicId: clearTopicFilter ? null : (selectedTopicId ?? this.selectedTopicId),
      selectedTopicName: clearTopicFilter ? null : (selectedTopicName ?? this.selectedTopicName),
    );
  }

  bool get hasTopicFilter => selectedTopicId != null;
}

class WeeklyNotifier extends StateNotifier<WeeklyState> {
  final Ref ref;

  WeeklyNotifier(this.ref) : super(WeeklyState());

  Future<void> loadCurrentWeek() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final apiClient = ref.read(apiClientProvider);
      final summary = await apiClient.getCurrentWeekSummary();
      state = state.copyWith(currentWeek: summary, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> loadSummaries() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final apiClient = ref.read(apiClientProvider);
      final summaries = await apiClient.getWeeklySummaries();
      state = state.copyWith(summaries: summaries, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  void setTopicFilter(int? topicId, String? name) {
    if (topicId == null) {
      state = state.copyWith(clearTopicFilter: true);
    } else {
      state = state.copyWith(selectedTopicId: topicId, selectedTopicName: name);
    }
  }

  /// Poll a kicked-off generation until it finishes, then load the summary.
  /// Generation runs server-side and can take minutes on the CPU VPS.
  Future<WeeklySummary> _awaitGeneration(ApiClient api, int summaryId) async {
    const maxAttempts = 200; // ~20 min at 6s between polls
    for (var i = 0; i < maxAttempts; i++) {
      await Future.delayed(const Duration(seconds: 6));
      final status = await api.getWeeklyGenerationStatus(summaryId);
      if (status.isCompleted) {
        return await api.getWeeklySummary(summaryId);
      }
      if (status.isFailed) {
        throw Exception(status.error ?? 'Generierung fehlgeschlagen');
      }
      // "idle" means the task was lost (e.g. server restart) — treat as failure.
      if (!status.isProcessing) {
        throw Exception('Generierung wurde unterbrochen');
      }
    }
    throw Exception('Zeitüberschreitung bei der Generierung');
  }

  Future<void> generateCurrentWeekSummary({bool showNotification = true}) async {
    state = state.copyWith(isGenerating: true, error: null);
    try {
      final apiClient = ref.read(apiClientProvider);
      final started = await apiClient.generateCurrentWeekSummary(
        topicId: state.selectedTopicId,
      );
      final summary = await _awaitGeneration(apiClient, started.summaryId);
      state = state.copyWith(currentWeek: summary, isGenerating: false);

      // Show notification if TL;DR is available
      if (showNotification && summary.hasTldr) {
        await NotificationService().showWeeklySummaryReady(
          tldr: summary.tldr!,
          weekId: summary.id,
        );
      }
    } catch (e) {
      state = state.copyWith(isGenerating: false, error: e.toString());
    }
  }

  Future<WeeklySummary?> loadSummaryDetails(int id) async {
    try {
      final apiClient = ref.read(apiClientProvider);
      return await apiClient.getWeeklySummary(id);
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return null;
    }
  }

  Future<WeeklySummary?> generateSummary(int id) async {
    state = state.copyWith(isGenerating: true, error: null);
    try {
      final apiClient = ref.read(apiClientProvider);
      final started = await apiClient.generateWeeklySummary(id);
      final summary = await _awaitGeneration(apiClient, started.summaryId);
      state = state.copyWith(isGenerating: false);
      return summary;
    } catch (e) {
      state = state.copyWith(isGenerating: false, error: e.toString());
      return null;
    }
  }
}

final weeklyProvider = StateNotifierProvider<WeeklyNotifier, WeeklyState>((ref) {
  return WeeklyNotifier(ref);
});
