import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';
import '../core/config/api_config.dart';

import 'dart:io';
import 'package:dio/dio.dart';

abstract class AiRepository {
  Future<Map<String, dynamic>> getAiStatus();
  Future<Map<String, dynamic>> detect({File? imageFile, String? demoScenario});
}

class AiRepositoryImpl implements AiRepository {
  final ApiService _api;

  AiRepositoryImpl(this._api);

  @override
  Future<Map<String, dynamic>> getAiStatus() async {
    final response = await _api.get('${ApiConfig.ai}/status');
    return response.data;
  }

  @override
  Future<Map<String, dynamic>> detect({File? imageFile, String? demoScenario}) async {
    final Map<String, dynamic> formMap = {
      'crop_type': 'Tomato',
      'field_id': 'field-001',
      'device_id': 'device-001',
    };
    if (imageFile != null) {
      formMap['file'] = await MultipartFile.fromFile(imageFile.path);
    } else {
      formMap['file'] = MultipartFile.fromBytes([0xFF, 0xD8, 0xFF, 0xE0], filename: 'leaf_scan.jpg');
    }
    final data = FormData.fromMap(formMap);

    Options? options;
    Map<String, dynamic>? queryParams;
    if (demoScenario != null && demoScenario.isNotEmpty) {
      options = Options(headers: {'X-Demo-Scenario': demoScenario});
      queryParams = {'demo_scenario': demoScenario};
    }

    final response = await _api.post(
      '${ApiConfig.ai}/detect',
      data: data,
      queryParameters: queryParams,
      options: options,
    );
    // The backend wraps every success payload in the standard {success, data}
    // envelope (see success_response). The detection payload —
    // {success, data, decision} — therefore arrives nested under `data`.
    // Unwrap one level so callers get the flat result they expect.
    final body = response.data as Map<String, dynamic>;
    final inner = body['data'];
    if (body['success'] == true && inner is Map) {
      return Map<String, dynamic>.from(inner);
    }
    return body; // error envelope: {success:false, error:{...}}
  }
}

final aiRepositoryProvider = Provider<AiRepository>((ref) {
  return AiRepositoryImpl(ref.read(apiServiceProvider));
});
