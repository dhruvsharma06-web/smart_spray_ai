import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';
import '../core/config/api_config.dart';

import 'dart:io';
import 'package:dio/dio.dart';

abstract class AiRepository {
  Future<Map<String, dynamic>> getAiStatus();
  Future<Map<String, dynamic>> detect({File? imageFile});
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
  Future<Map<String, dynamic>> detect({File? imageFile}) async {
    dynamic data;
    if (imageFile != null) {
      data = FormData.fromMap({
        'file': await MultipartFile.fromFile(imageFile.path),
      });
    }
    final response = await _api.post('${ApiConfig.ai}/detect', data: data);
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
