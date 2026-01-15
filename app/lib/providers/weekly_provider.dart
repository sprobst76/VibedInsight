import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/content_item.dart';
import '../services/notification_service.dart';
import 'api_provider.dart';

class WeeklyState {
  final WeeklySummary? currentWeek;
  final List<WeeklySummaryListItem> summaries;
  final bool isLoading;
  final bool isGenerating;
  final String? error;

  WeeklyState({
    this.currentWeek,
    this.summaries = const [],
    this.isLoading = false,
    this.isGenerating = false,
    this.error,
  });

  WeeklyState copyWith({
    WeeklySummary? currentWeek,
    List<WeeklySummaryListItem>? summaries,
    bool? isLoading,
    bool? isGenerating,
    String? error,
  }) {
    return WeeklyState(
      currentWeek: currentWeek ?? this.currentWeek,
      summaries: summaries ?? this.summaries,
      isLoading: isLoading ?? this.isLoading,
      isGenerating: isGenerating ?? this.isGenerating,
      error: error,
    );
  }
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

  Future<void> generateCurrentWeekSummary({bool showNotification = true}) async {
    state = state.copyWith(isGenerating: true, error: null);
    try {
      final apiClient = ref.read(apiClientProvider);
      final summary = await apiClient.generateCurrentWeekSummary();
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
      final summary = await apiClient.generateWeeklySummary(id);
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
