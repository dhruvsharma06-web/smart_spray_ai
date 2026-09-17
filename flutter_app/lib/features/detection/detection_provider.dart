import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../repositories/ai_repository.dart';

enum DetectionStatus {
  idle,
  scanning,
  resultReady,
  spraying,
  error,
  offline,
}

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
    bool clearResult = false,
    bool clearError = false,
  }) {
    return DetectionState(
      status: status ?? this.status,
      aiResult: clearResult ? null : (aiResult ?? this.aiResult),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class DetectionStateNotifier extends Notifier<DetectionState> {
  @override
  DetectionState build() {
    return const DetectionState();
  }

  // ------------------------------------------------------------
  // AI SCAN
  // ------------------------------------------------------------

  Future<void> startScan({
    File? imageFile,
    String? demoScenario,
  }) async {
    state = state.copyWith(
      status: DetectionStatus.scanning,
      clearError: true,
      clearResult: true,
    );

    try {
      final res = await ref.read(aiRepositoryProvider).detect(
            imageFile: imageFile,
            demoScenario: demoScenario,
          );

      // Successful response
      if (res['success'] == true) {
        state = state.copyWith(
          status: DetectionStatus.resultReady,
          aiResult: res,
          clearError: true,
        );
        return;
      }

      // Backend responded but analysis failed.
      String message = 'Analysis failed';

      final error = res['error'];

      if (error is Map && error['message'] != null) {
        message = error['message'].toString();
      } else if (res['message'] != null) {
        message = res['message'].toString();
      } else if (res['detail'] != null) {
        message = res['detail'].toString();
      }

      message = _friendlyMessage(message);

      state = state.copyWith(
        status: DetectionStatus.error,
        errorMessage: message,
      );
    } on DioException catch (e) {
      // Actual network/connectivity problem
      final isNetworkError =
          e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout;

      if (isNetworkError) {
        state = state.copyWith(
          status: DetectionStatus.offline,
          errorMessage: 'Backend API offline',
        );
        return;
      }

      // Backend was reached but returned HTTP error.
      String message = 'Analysis failed';

      final responseData = e.response?.data;

      if (responseData is Map) {
        final data = Map<String, dynamic>.from(responseData);

        final error = data['error'];

        if (error is Map && error['message'] != null) {
          message = error['message'].toString();
        } else if (data['message'] != null) {
          message = data['message'].toString();
        } else if (data['detail'] != null) {
          message = data['detail'].toString();
        }
      }

      message = _friendlyMessage(message);

      state = state.copyWith(
        status: DetectionStatus.error,
        errorMessage: message,
      );
    } catch (e) {
      state = state.copyWith(
        status: DetectionStatus.error,
        errorMessage: 'Analysis failed: $e',
      );
    }
  }

  // ------------------------------------------------------------
  // FRIENDLY ERROR MESSAGES
  // ------------------------------------------------------------

  String _friendlyMessage(String message) {
    final lower = message.toLowerCase();

    if (lower.contains('no plant') ||
        lower.contains('plant not detected') ||
        lower.contains('no crop') ||
        lower.contains('crop not detected') ||
        lower.contains('no vegetation')) {
      return 'No plant detected. Please point the camera at a crop.';
    }

    return message;
  }

  // ------------------------------------------------------------
  // DETECTION RESULT ACTIONS
  // ------------------------------------------------------------

  void skip() {
    state = state.copyWith(
      status: DetectionStatus.idle,
      clearResult: true,
      clearError: true,
    );
  }

  Future<void> spray() async {
    state = state.copyWith(
      status: DetectionStatus.spraying,
      clearError: true,
    );

    // The actual actuator command is handled by the
    // control/spray module. This state change keeps the
    // detection screen API compatible.
  }

  void startSpraying() {
    state = state.copyWith(
      status: DetectionStatus.spraying,
      clearError: true,
    );
  }

  void finishSpraying() {
    state = state.copyWith(
      status: DetectionStatus.resultReady,
    );
  }

  // ------------------------------------------------------------
  // RESET
  // ------------------------------------------------------------

  void reset() {
    state = const DetectionState();
  }
}

final detectionStateProvider =
    NotifierProvider<DetectionStateNotifier, DetectionState>(
  DetectionStateNotifier.new,
);