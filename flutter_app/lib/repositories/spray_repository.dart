import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';
import '../core/config/api_config.dart';

abstract class SprayRepository {
  Future<void> sprayManual(String deviceId, double duration);
  Future<void> stopSpray(String deviceId);
  Future<void> emergencyStop();
  Future<void> resetEmergencyStop();
}

class SprayRepositoryImpl implements SprayRepository {
  final ApiService _api;

  SprayRepositoryImpl(this._api);

  @override
  Future<void> sprayManual(String deviceId, double duration) async {
    try {
      await _api.post('${ApiConfig.spray}/manual', data: {
        'device_id': deviceId,
        'duration_ms': (duration * 1000).toInt(),
        'command_id': DateTime.now().millisecondsSinceEpoch.toString(),
      });
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<void> stopSpray(String deviceId) async {
    try {
      await _api.post('${ApiConfig.spray}/stop', data: {'device_id': deviceId});
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<void> emergencyStop() async {
    try {
      await _api.post('${ApiConfig.spray}/emergency-stop');
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<void> resetEmergencyStop() async {
    try {
      await _api.post('${ApiConfig.spray}/reset-emergency-stop');
    } catch (e) {
      rethrow;
    }
  }
}

final sprayRepositoryProvider = Provider<SprayRepository>((ref) {
  return SprayRepositoryImpl(ref.read(apiServiceProvider));
});
