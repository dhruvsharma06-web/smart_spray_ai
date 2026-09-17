import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../repositories/spray_repository.dart';


class ControlState {
  final double sprayDuration;
  final bool isSpraying;
  final bool isEmergencyStopped;

  const ControlState({

    this.sprayDuration = 1.0,
    this.isSpraying = false,
    this.isEmergencyStopped = false,
  });

  ControlState copyWith({
    double? sprayDuration,
    bool? isSpraying,
    bool? isEmergencyStopped,
  }) {
    return ControlState(

      sprayDuration: sprayDuration ?? this.sprayDuration,
      isSpraying: isSpraying ?? this.isSpraying,
      isEmergencyStopped: isEmergencyStopped ?? this.isEmergencyStopped,
    );
  }
}

class ControlStateNotifier extends Notifier<ControlState> {
  @override
  ControlState build() => const ControlState();


  void setSprayDuration(double duration) {
    if (state.isEmergencyStopped || state.isSpraying) return;
    state = state.copyWith(sprayDuration: duration);
  }

  void startSpray() async {
    if (state.isEmergencyStopped || state.isSpraying) return;
    state = state.copyWith(isSpraying: true);
    try {
      await ref.read(sprayRepositoryProvider).sprayManual('device-001', state.sprayDuration);
      await Future.delayed(Duration(milliseconds: (state.sprayDuration * 1000).toInt()));
    } catch (_) {
      // Spray failure is reflected by not clearing isSpraying below
    }

    if (state.isSpraying) {
      state = state.copyWith(isSpraying: false);
    }
  }

  void stopSpray() async {
    state = state.copyWith(isSpraying: false);
    try {
      await ref.read(sprayRepositoryProvider).stopSpray('device-001');
    } catch (_) {
      // Best-effort stop; UI already reflects stopped state
    }
  }

  void emergencyStop() async {
    state = state.copyWith(isSpraying: false, isEmergencyStopped: true);
    try {
      await ref.read(sprayRepositoryProvider).emergencyStop();
    } catch (_) {
      // Best-effort emergency stop; UI already reflects e-stop state
    }
  }

  void resetEmergencyStop() async {
    state = state.copyWith(isEmergencyStopped: false);
    try {
      await ref.read(sprayRepositoryProvider).resetEmergencyStop();
    } catch (_) {
      // Best-effort reset; UI already reflects reset state
    }
  }


}

final controlStateProvider = NotifierProvider<ControlStateNotifier, ControlState>(() {
  return ControlStateNotifier();
});
