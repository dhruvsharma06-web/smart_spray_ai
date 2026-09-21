import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../repositories/spray_repository.dart';
import '../../repositories/device_repository.dart';

String extractSafetyErrorMessage(dynamic e, String action) {
  if (e is DioException) {
    dynamic resData = e.response?.data;
    if (resData is String) {
      try {
        resData = jsonDecode(resData);
      } catch (_) {}
    }
    if (resData is Map) {
      final detail = resData['detail'];
      if (detail is Map) {
        final msg = detail['message'] ?? detail['reason'];
        if (msg != null && msg.toString().isNotEmpty) {
          return '$action blocked: $msg';
        }
      } else if (detail is String && detail.isNotEmpty) {
        return '$action blocked: $detail';
      }
      final msg = resData['message'] ?? resData['reason'];
      if (msg != null && msg.toString().isNotEmpty) {
        return '$action blocked: $msg';
      }
    } else if (resData is String && resData.isNotEmpty) {
      return '$action blocked: $resData';
    }
    if (e.message != null && e.message!.isNotEmpty) {
      return '$action blocked: ${e.message}';
    }
  }
  return '$action blocked: $e';
}

class ControlState {
  final double sprayDuration;
  final double irrigationDuration;
  final bool isSpraying;
  final bool isIrrigating;
  final bool isQueued;
  final bool isEmergencyStopped;
  final String? statusMessage;
  final String? errorMessage;

  const ControlState({
    this.sprayDuration = 5.0,
    this.irrigationDuration = 10.0,
    this.isSpraying = false,
    this.isIrrigating = false,
    this.isQueued = false,
    this.isEmergencyStopped = false,
    this.statusMessage,
    this.errorMessage,
  });

  ControlState copyWith({
    double? sprayDuration,
    double? irrigationDuration,
    bool? isSpraying,
    bool? isIrrigating,
    bool? isQueued,
    bool? isEmergencyStopped,
    String? statusMessage,
    String? errorMessage,
    bool clearStatus = false,
    bool clearError = false,
  }) {
    return ControlState(
      sprayDuration: sprayDuration ?? this.sprayDuration,
      irrigationDuration: irrigationDuration ?? this.irrigationDuration,
      isSpraying: isSpraying ?? this.isSpraying,
      isIrrigating: isIrrigating ?? this.isIrrigating,
      isQueued: isQueued ?? this.isQueued,
      isEmergencyStopped: isEmergencyStopped ?? this.isEmergencyStopped,
      statusMessage: clearStatus ? null : (statusMessage ?? this.statusMessage),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class ControlStateNotifier extends Notifier<ControlState> {
  @override
  ControlState build() => const ControlState();

  void setSprayDuration(double duration) {
    if (state.isEmergencyStopped || state.isSpraying || state.isIrrigating) return;
    state = state.copyWith(sprayDuration: duration);
  }

  void setIrrigationDuration(double duration) {
    if (state.isEmergencyStopped || state.isSpraying || state.isIrrigating) return;
    state = state.copyWith(irrigationDuration: duration);
  }

  Future<void> startSpray() async {
    if (state.isEmergencyStopped || state.isSpraying || state.isIrrigating) return;
    state = state.copyWith(isSpraying: false, isQueued: true, clearStatus: true, clearError: true);
    try {
      final res = await ref.read(sprayRepositoryProvider).sprayManual('device-001', state.sprayDuration);
      final isQueued = res['status'] == 'QUEUED' || res['success'] == true;
      state = state.copyWith(
        isQueued: isQueued,
        statusMessage: isQueued ? 'Spray command queued. Awaiting ESP32 poll...' : 'Spray command sent',
      );

      // Poll real device status to observe pump START and COMPLETE acknowledgements
      final deviceRepo = ref.read(deviceRepositoryProvider);
      final maxPolls = (state.sprayDuration + 10).toInt() * 2; // poll every 500ms
      bool started = false;

      for (int i = 0; i < maxPolls; i++) {
        await Future.delayed(const Duration(milliseconds: 500));
        try {
          final status = await deviceRepo.getDeviceStatus('device-001');
          final currentAction = (status['current_action'] as String?)?.toUpperCase() ?? 'IDLE';
          final pumpStatus = (status['pump_status'] as String?)?.toLowerCase() ?? 'off';

          if (!started && (currentAction == 'SPRAYING' || pumpStatus == 'on')) {
            started = true;
            state = state.copyWith(
              isSpraying: true,
              isQueued: false,
              statusMessage: 'ESP32 Spraying active (Relay CH2/GPIO25 ON)',
            );
          } else if (started && currentAction == 'IDLE' && pumpStatus == 'off') {
            state = state.copyWith(
              isSpraying: false,
              isQueued: false,
              statusMessage: 'ESP32 Spray completed successfully (Relay OFF)',
            );
            break;
          }
        } catch (_) {
          // Continue polling
        }
      }
    } catch (e) {
      final cleanError = extractSafetyErrorMessage(e, 'Spray');
      state = state.copyWith(
        isSpraying: false,
        isQueued: false,
        errorMessage: cleanError,
      );
    } finally {
      if (state.isSpraying || state.isQueued) {
        state = state.copyWith(isSpraying: false, isQueued: false);
      }
    }
  }

  Future<void> startIrrigation() async {
    if (state.isEmergencyStopped || state.isSpraying || state.isIrrigating) return;
    state = state.copyWith(isIrrigating: false, isQueued: true, clearStatus: true, clearError: true);
    try {
      final res = await ref.read(sprayRepositoryProvider).irrigateManual('device-001', state.irrigationDuration);
      final isQueued = res['status'] == 'QUEUED' || res['success'] == true;
      state = state.copyWith(
        isQueued: isQueued,
        statusMessage: isQueued ? 'Irrigation command queued. Awaiting ESP32 poll...' : 'Irrigation command sent',
      );

      final deviceRepo = ref.read(deviceRepositoryProvider);
      final maxPolls = (state.irrigationDuration + 10).toInt() * 2;
      bool started = false;

      for (int i = 0; i < maxPolls; i++) {
        await Future.delayed(const Duration(milliseconds: 500));
        try {
          final status = await deviceRepo.getDeviceStatus('device-001');
          final currentAction = (status['current_action'] as String?)?.toUpperCase() ?? 'IDLE';
          final pumpStatus = (status['pump_status'] as String?)?.toLowerCase() ?? 'off';

          if (!started && (currentAction == 'IRRIGATING' || pumpStatus == 'on')) {
            started = true;
            state = state.copyWith(
              isIrrigating: true,
              isQueued: false,
              statusMessage: 'ESP32 Irrigation active (Relay CH1/GPIO26 ON)',
            );
          } else if (started && currentAction == 'IDLE' && pumpStatus == 'off') {
            state = state.copyWith(
              isIrrigating: false,
              isQueued: false,
              statusMessage: 'ESP32 Irrigation completed successfully (Relay OFF)',
            );
            break;
          }
        } catch (_) {
          // Continue polling
        }
      }
    } catch (e) {
      final cleanError = extractSafetyErrorMessage(e, 'Irrigation');
      state = state.copyWith(
        isIrrigating: false,
        isQueued: false,
        errorMessage: cleanError,
      );
    } finally {
      if (state.isIrrigating || state.isQueued) {
        state = state.copyWith(isIrrigating: false, isQueued: false);
      }
    }
  }

  Future<void> stopSpray() async {
    state = state.copyWith(isSpraying: false, isIrrigating: false, isQueued: false, statusMessage: 'Actuators stopped');
    try {
      await ref.read(sprayRepositoryProvider).stopSpray('device-001');
    } catch (e) {
      state = state.copyWith(errorMessage: extractSafetyErrorMessage(e, 'Stop'));
    }
  }

  Future<void> emergencyStop() async {
    state = state.copyWith(
      isSpraying: false,
      isIrrigating: false,
      isQueued: false,
      isEmergencyStopped: true,
      statusMessage: 'EMERGENCY CUTOFF ENGAGED - All pumps isolated',
    );
    try {
      await ref.read(sprayRepositoryProvider).emergencyStop(deviceId: 'device-001');
    } catch (e) {
      state = state.copyWith(errorMessage: extractSafetyErrorMessage(e, 'Emergency stop'));
    }
  }

  Future<void> resetEmergencyStop() async {
    try {
      await ref.read(sprayRepositoryProvider).resetEmergencyStop(deviceId: 'device-001');
      state = state.copyWith(
        isEmergencyStopped: false,
        statusMessage: 'Emergency lock cleared. System restored ONLINE.',
        clearError: true,
      );
    } catch (e) {
      state = state.copyWith(errorMessage: extractSafetyErrorMessage(e, 'Reset'));
    }
  }
}

final controlStateProvider = NotifierProvider<ControlStateNotifier, ControlState>(() {
  return ControlStateNotifier();
});
