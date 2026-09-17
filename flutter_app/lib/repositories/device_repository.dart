import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';
import '../core/config/api_config.dart';

abstract class DeviceRepository {
  Future<Map<String, dynamic>> getDeviceStatus(String deviceId);
  Future<void> setDeviceMode(String deviceId, String mode);
}

class DeviceRepositoryImpl implements DeviceRepository {
  final ApiService _api;

  DeviceRepositoryImpl(this._api);

  @override
  Future<Map<String, dynamic>> getDeviceStatus(String deviceId) async {
    try {
      final response = await _api.get('${ApiConfig.devices}/$deviceId/status');
      return response.data;
    } catch (e) { rethrow; }
  }

  @override
  Future<void> setDeviceMode(String deviceId, String mode) async {
    try {
      await _api.post('${ApiConfig.devices}/$deviceId/mode', data: {'mode': mode});
    } catch (e) { rethrow; }
  }
}

final deviceRepositoryProvider = Provider<DeviceRepository>((ref) {
  final api = ref.read(apiServiceProvider);
  return DeviceRepositoryImpl(api);
});
