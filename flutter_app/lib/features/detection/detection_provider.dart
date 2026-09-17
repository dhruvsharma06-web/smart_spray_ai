import 'dart:io';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../repositories/ai_repository.dart';
import '../../repositories/spray_repository.dart';

enum DetectionStatus { idle, scanning, resultReady, spraying, error, offline }

class DetectionState {
  final DetectionStatus status;
  final Map<String, dynamic>? aiResult;
  final String? errorMessage;

  const DetectionState({
    this.status = DetectionStatus.idle,
    this.aiResult,
    this.errorMessage,
  });

  DetectionState copyWith({
    DetectionStatus? status,
    Map<String, dynamic>? aiResult,
    String? errorMessage,
  }) {
    return DetectionState(
      status: status ?? this.status,
      aiResult: aiResult ?? this.aiResult,
      errorMessage: errorMessage,
    );
  }
}

class DetectionStateNotifier extends Notifier<DetectionState> {
  @override
  DetectionState build() => const DetectionState();

  void startScan({File? imageFile, String? demoScenario}) async {
    state = state.copyWith(status: DetectionStatus.scanning);
    try {
      final res = await ref
          .read(aiRepositoryProvider)
          .detect(imageFile: imageFile, demoScenario: demoScenario);
      if (res['success'] == true) {
        state =
            state.copyWith(status: DetectionStatus.resultReady, aiResult: res);
      } else {
        state = state.copyWith(
            status: DetectionStatus.error,
            errorMessage: "Detection failed: ${res['error']}");
      }
    } catch (e) {
      state = state.copyWith(
          status: DetectionStatus.offline, errorMessage: "Backend API offline");
    }
  }

  void spray() async {
    if (state.status != DetectionStatus.resultReady) return;

    // Auto-spray based on AI
    final decision = state.aiResult?['decision'];
    if (decision == null || decision['auto_permitted'] == false) {
      state = state.copyWith(
          status: DetectionStatus.error,
          errorMessage: "Spray not permitted by AI constraints.");
      return;
    }

    final decisionId = decision['decision_id'] as String?;
    if (decisionId == null || decisionId.isEmpty) {
      state = state.copyWith(
          status: DetectionStatus.error,
          errorMessage: "No valid decision ID available for spray authorization.");
      return;
    }

    state = state.copyWith(status: DetectionStatus.spraying);
    try {
      await ref
          .read(sprayRepositoryProvider)
          .sprayManual('device-001', 1.0, decisionId: decisionId);
      await Future.delayed(const Duration(seconds: 2));
      state = const DetectionState(status: DetectionStatus.idle);
    } catch (e) {
      state = state.copyWith(
          status: DetectionStatus.error, errorMessage: "Spray command failed: $e");
    }
  }

  void skip() {
    state = const DetectionState(status: DetectionStatus.idle);
  }

  void reset() {
    state = const DetectionState(status: DetectionStatus.idle);
  }
}

final detectionStateProvider =
    NotifierProvider<DetectionStateNotifier, DetectionState>(() {
  return DetectionStateNotifier();
});
