import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/config/api_config.dart';
import '../services/api_service.dart';

class FieldStatistics {
  final String fieldId;
  final String deviceId;
  final String healthSummary;
  final int recentScansCount;
  final Map<String, dynamic>? latestDetection;
  final int totalActions;
  final int totalSprays;
  final int totalIrrigations;
  final int totalCompleted;
  final Map<String, dynamic>? latestOperation;
  final Map<String, dynamic> telemetry;

  FieldStatistics({
    required this.fieldId,
    required this.deviceId,
    required this.healthSummary,
    required this.recentScansCount,
    this.latestDetection,
    required this.totalActions,
    required this.totalSprays,
    required this.totalIrrigations,
    required this.totalCompleted,
    this.latestOperation,
    required this.telemetry,
  });

  factory FieldStatistics.empty() {
    return FieldStatistics(
      fieldId: 'field-001',
      deviceId: 'device-001',
      healthSummary: 'NO_DATA',
      recentScansCount: 0,
      latestDetection: null,
      totalActions: 0,
      totalSprays: 0,
      totalIrrigations: 0,
      totalCompleted: 0,
      latestOperation: null,
      telemetry: {},
    );
  }

  factory FieldStatistics.fromJson(Map<String, dynamic> json) {
    final health = json['field_health'] is Map ? json['field_health'] as Map : {};
    final ops = json['operations'] is Map ? json['operations'] as Map : {};
    final telem = json['telemetry'] is Map ? Map<String, dynamic>.from(json['telemetry']) : <String, dynamic>{};

    return FieldStatistics(
      fieldId: json['field_id'] ?? 'field-001',
      deviceId: json['device_id'] ?? 'device-001',
      healthSummary: health['summary'] ?? 'NO_DATA',
      recentScansCount: health['recent_scans_count'] ?? 0,
      latestDetection: health['latest_detection'] is Map ? Map<String, dynamic>.from(health['latest_detection']) : null,
      totalActions: ops['total_actions'] ?? 0,
      totalSprays: ops['total_sprays'] ?? 0,
      totalIrrigations: ops['total_irrigations'] ?? 0,
      totalCompleted: ops['total_completed'] ?? 0,
      latestOperation: ops['latest_operation'] is Map ? Map<String, dynamic>.from(ops['latest_operation']) : null,
      telemetry: telem,
    );
  }
}

abstract class StatisticsRepository {
  Future<FieldStatistics> getStatistics({String fieldId = 'field-001', String deviceId = 'device-001'});
}

class StatisticsRepositoryImpl implements StatisticsRepository {
  final ApiService _api;

  StatisticsRepositoryImpl(this._api);

  @override
  Future<FieldStatistics> getStatistics({String fieldId = 'field-001', String deviceId = 'device-001'}) async {
    try {
      final res = await _api.get(
        ApiConfig.statistics,
        queryParameters: {'field_id': fieldId, 'device_id': deviceId},
      );
      return FieldStatistics.fromJson(Map<String, dynamic>.from(res.data));
    } catch (e) {
      rethrow;
    }
  }
}

final statisticsRepositoryProvider = Provider<StatisticsRepository>((ref) {
  final api = ref.read(apiServiceProvider);
  return StatisticsRepositoryImpl(api);
});

// Periodic poller for field statistics (every 10 seconds)
final liveStatisticsProvider = StreamProvider.autoDispose<FieldStatistics>((ref) async* {
  final repo = ref.read(statisticsRepositoryProvider);
  while (true) {
    try {
      final stats = await repo.getStatistics();
      yield stats;
    } catch (_) {
      // Yield empty state on failure so UI does not remain stuck on a loading spinner
      yield FieldStatistics.empty();
    }
    await Future.delayed(const Duration(seconds: 10));
  }
});
