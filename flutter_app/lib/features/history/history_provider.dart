import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/config/api_config.dart';
import '../../services/api_service.dart';


enum HistoryFilter { all, sprayed, skipped, failed }

class HistoryState {
  final List<dynamic> events;
  final HistoryFilter filter;
  final bool isLoading;
  final String? error;

  const HistoryState({
    this.events = const [],
    this.filter = HistoryFilter.all,
    this.isLoading = false,
    this.error,
  });

  HistoryState copyWith({
    List<dynamic>? events,
    HistoryFilter? filter,
    bool? isLoading,
    String? error,
  }) {
    return HistoryState(
      events: events ?? this.events,
      filter: filter ?? this.filter,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }

  List<dynamic> get filteredEvents {
    switch (filter) {
      case HistoryFilter.all:
        return events;
      case HistoryFilter.sprayed:
        return events.where((e) => e['status']?.toLowerCase() == 'completed').toList();
      case HistoryFilter.skipped:
        return events.where((e) => e['status']?.toLowerCase() == 'skipped').toList();
      case HistoryFilter.failed:
        return events.where((e) => e['status']?.toLowerCase() == 'failed' || e['status']?.toLowerCase() == 'error').toList();
    }
  }
}

class HistoryStateNotifier extends Notifier<HistoryState> {
  @override
  HistoryState build() {
    Future.microtask(() => loadEvents());
    return const HistoryState();
  }

  Future<void> loadEvents() async {
    state = state.copyWith(isLoading: true);
    try {
      final res = await ref.read(apiServiceProvider).get('${ApiConfig.spray}/history');
      if (res.data != null) {
        if (res.data is List) {
          state = state.copyWith(events: res.data as List<dynamic>, isLoading: false, error: null);
        } else if (res.data is Map && res.data['data'] is List) {
          state = state.copyWith(events: res.data['data'] as List<dynamic>, isLoading: false, error: null);
        } else {
          state = state.copyWith(isLoading: false, error: "Invalid response");
        }
      } else {
        state = state.copyWith(isLoading: false, error: "Empty response");
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  void setFilter(HistoryFilter filter) {
    state = state.copyWith(filter: filter);
  }
}

final historyStateProvider = NotifierProvider<HistoryStateNotifier, HistoryState>(() {
  return HistoryStateNotifier();
});
