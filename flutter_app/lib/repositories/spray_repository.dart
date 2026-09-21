import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';
import '../core/config/api_config.dart';

abstract class SprayRepository {
  Future<Map<String, dynamic>> sprayManual(String deviceId, double duration, {String? decisionId});
  Future<Map<String, dynamic>> irrigateManual(String deviceId, double duration, {String? decisionId});
  Future<Map<String, dynamic>> stopSpray(String deviceId);
  Future<Map<String, dynamic>> emergencyStop({String? deviceId});
  Future<Map<String, dynamic>> resetEmergencyStop({String? deviceId});
}

class SprayRepositoryImpl implements SprayRepository {
  final ApiService _api;

  SprayRepositoryImpl(this._api);

  @override
  Future<Map<String, dynamic>> sprayManual(String deviceId, double duration, {String? decisionId}) async {
    try {
      final Map<String, dynamic> payload = {
        'device_id': deviceId,
        'duration_ms': (duration * 1000).toInt(),
        'command_id': DateTime.now().millisecondsSinceEpoch.toString(),
      };
      if (decisionId != null && decisionId.isNotEmpty) {
        payload['decision_id'] = decisionId;
      }
      final res = await _api.post('${ApiConfig.spray}/manual', data: payload);
      return Map<String, dynamic>.from(res.data);
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<Map<String, dynamic>> irrigateManual(String deviceId, double duration, {String? decisionId}) async {
    try {
      final Map<String, dynamic> payload = {
        'device_id': deviceId,
        'duration_ms': (duration * 1000).toInt(),
        'command_id': DateTime.now().millisecondsSinceEpoch.toString(),
      };
      if (decisionId != null && decisionId.isNotEmpty) {
        payload['decision_id'] = decisionId;
      }
      final res = await _api.post('${ApiConfig.spray}/irrigate', data: payload);
      return Map<String, dynamic>.from(res.data);
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<Map<String, dynamic>> stopSpray(String deviceId) async {
    try {
      final res = await _api.post('${ApiConfig.spray}/stop', data: {'device_id': deviceId});
      return Map<String, dynamic>.from(res.data);
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<Map<String, dynamic>> emergencyStop({String? deviceId}) async {
    try {
      final res = await _api.post('${ApiConfig.spray}/emergency-stop', data: {'device_id': deviceId ?? 'device-001'});
      return Map<String, dynamic>.from(res.data);
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<Map<String, dynamic>> resetEmergencyStop({String? deviceId}) async {
    try {
      final res = await _api.post('${ApiConfig.spray}/reset-emergency-stop', data: {'device_id': deviceId ?? 'device-001'});
      return Map<String, dynamic>.from(res.data);
    } catch (e) {
      rethrow;
    }
  }
}

final sprayRepositoryProvider = Provider<SprayRepository>((ref) {
  return SprayRepositoryImpl(ref.read(apiServiceProvider));
});
