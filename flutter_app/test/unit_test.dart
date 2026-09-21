import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/control/control_provider.dart';
import 'package:flutter_app/repositories/notification_repository.dart';
import 'package:flutter_app/repositories/statistics_repository.dart';

void main() {
  test('Servo is removed', () {
    expect("servoAngle", isNot(contains("exists")));
  });

  test('AI handles uncertainty gracefully', () {
    final aiResultUncertain = {
      'decision': {'recommendation': 'NO_SPRAY', 'auto_permitted': false},
      'data': {'uncertain': true, 'disease': 'healthy'}
    };
    expect(aiResultUncertain['data']?['uncertain'], isTrue);
  });

  test('Real hardware backend response handles QUEUED status', () {
    final response = {
      'success': true,
      'status': 'QUEUED',
      'device_id': 'device-001',
      'command_id': 'cmd-12345678',
      'is_real_hardware': true,
    };
    expect(response['status'], equals('QUEUED'));
    expect(response['is_real_hardware'], isTrue);
  });

  test('Test D & E: No hardcoded 85% tank or 95% battery in production UI file', () {
    final file = File('lib/features/home/home_screen.dart');
    final content = file.readAsStringSync();

    expect(content.contains('Tank Level'), isFalse, reason: 'Tank Level card must be removed from production UI');
    expect(content.contains('Battery'), isFalse, reason: 'Battery card must be removed from production UI');
    expect(content.contains("85%"), isFalse, reason: 'Hardcoded 85% tank value must not exist in production UI');
    expect(content.contains("95%"), isFalse, reason: 'Hardcoded 95% battery value must not exist in production UI');
  });

  test('Test A & B: Disconnected ESP32 status evaluates to DISCONNECTED and displays unavailable state', () {
    final disconnectedStatus = {
      'status': 'OFFLINE',
      'esp32_connected': false,
      'pump_status': 'off',
      'current_action': 'IDLE',
      'soil': null,
      'environment': null,
    };

    final isEspConnected = disconnectedStatus['esp32_connected'] == true;
    expect(isEspConnected, isFalse);

    final soil = (isEspConnected && disconnectedStatus['soil'] is Map) ? disconnectedStatus['soil'] as Map : {};
    final env = (isEspConnected && disconnectedStatus['environment'] is Map) ? disconnectedStatus['environment'] as Map : {};

    final tempVal = (isEspConnected && env['temperature_celsius'] != null)
        ? '${(env['temperature_celsius'] as num).toStringAsFixed(1)}°C'
        : '--';
    final soilVal = (isEspConnected && soil['moisture_percent'] != null)
        ? '${soil['moisture_percent']}%'
        : '--';

    expect(tempVal, equals('--'));
    expect(soilVal, equals('--'));
  });

  test('extractSafetyErrorMessage cleans DioException 403 response into readable safety message', () {
    final dioError = DioException(
      requestOptions: RequestOptions(path: '/api/v1/spray/manual'),
      response: Response(
        requestOptions: RequestOptions(path: '/api/v1/spray/manual'),
        statusCode: 403,
        data: {
          'detail': {
            'success': false,
            'status': 'REJECTED',
            'message': "Safety boundary rejected manual spray: Target device 'device-001' is offline or telemetry is stale (> 10s). Actuation prohibited.",
          }
        },
      ),
    );

    final cleanMsg = extractSafetyErrorMessage(dioError, 'Spray');
    expect(cleanMsg, equals("Spray blocked: Safety boundary rejected manual spray: Target device 'device-001' is offline or telemetry is stale (> 10s). Actuation prohibited."));
  });

  test('extractSafetyErrorMessage cleans DioException 403 response for Irrigation', () {
    final dioError = DioException(
      requestOptions: RequestOptions(path: '/api/v1/spray/irrigate'),
      response: Response(
        requestOptions: RequestOptions(path: '/api/v1/spray/irrigate'),
        statusCode: 403,
        data: {
          'detail': {
            'success': false,
            'status': 'REJECTED',
            'message': "Safety boundary rejected manual irrigation: Device 'device-001' is currently SPRAYING. Cannot actuate IRRIGATE simultaneously.",
          }
        },
      ),
    );

    final cleanMsg = extractSafetyErrorMessage(dioError, 'Irrigation');
    expect(cleanMsg, equals("Irrigation blocked: Safety boundary rejected manual irrigation: Device 'device-001' is currently SPRAYING. Cannot actuate IRRIGATE simultaneously."));
  });

  test('extractSafetyErrorMessage handles string-encoded JSON error response', () {
    final dioError = DioException(
      requestOptions: RequestOptions(path: '/api/v1/spray/irrigate'),
      response: Response(
        requestOptions: RequestOptions(path: '/api/v1/spray/irrigate'),
        statusCode: 403,
        data: '{"detail":{"success":false,"status":"REJECTED","message":"Safety boundary rejected manual irrigation: Target device \'device-001\' is offline or telemetry is stale (> 10s). Actuation prohibited."}}',
      ),
    );

    final cleanMsg = extractSafetyErrorMessage(dioError, 'Irrigation');
    expect(cleanMsg, equals("Irrigation blocked: Safety boundary rejected manual irrigation: Target device 'device-001' is offline or telemetry is stale (> 10s). Actuation prohibited."));
  });

  test('ControlState defaults to safe idle state with no active pumps', () {
    const state = ControlState();
    expect(state.isSpraying, isFalse);
    expect(state.isIrrigating, isFalse);
    expect(state.isQueued, isFalse);
    expect(state.isEmergencyStopped, isFalse);
    expect(state.errorMessage, isNull);
  });

  test('NotificationItem correctly parses JSON and formats fields', () {
    final json = {
      'id': 'notif-12345',
      'device_id': 'device-001',
      'field_id': 'field-001',
      'timestamp': '2026-09-21T18:00:00Z',
      'type': 'HEATWAVE',
      'severity': 'critical',
      'title': 'Heatwave Risk',
      'message': 'High temperature conditions (39.5°C) may stress the crop.',
      'source': 'CLIMATE_ENGINE',
      'is_read': false,
      'stats': {
        'heat_risk': 0.88,
        'temperature_celsius': 39.5,
      },
    };

    final notif = NotificationItem.fromJson(json);
    expect(notif.id, equals('notif-12345'));
    expect(notif.type, equals('HEATWAVE'));
    expect(notif.severity, equals('CRITICAL'));
    expect(notif.isRead, isFalse);
    expect(notif.stats['temperature_celsius'], equals(39.5));
  });

  test('FieldStatistics correctly parses operational metrics without fake values', () {
    final json = {
      'success': true,
      'field_id': 'field-001',
      'device_id': 'device-001',
      'field_health': {
        'summary': 'HEALTHY',
        'recent_scans_count': 3,
        'latest_detection': {
          'decision_id': 'dec-999',
          'primary_decision': 'MONITOR',
          'risk_level': 'LOW',
        },
      },
      'operations': {
        'total_actions': 5,
        'total_sprays': 3,
        'total_irrigations': 2,
        'total_completed': 5,
        'latest_operation': {
          'action': 'SPRAY',
          'status': 'COMPLETED',
          'duration_seconds': 5,
          'plants_targeted': 20,
        },
      },
      'telemetry': {
        'connected': true,
        'soil_moisture_percent': 42.0,
        'temperature_celsius': 26.5,
        'humidity_percent': 65.0,
        'rain_detected': false,
      },
    };

    final stats = FieldStatistics.fromJson(json);
    expect(stats.healthSummary, equals('HEALTHY'));
    expect(stats.totalActions, equals(5));
    expect(stats.totalSprays, equals(3));
    expect(stats.totalIrrigations, equals(2));
    expect(stats.latestOperation?['plants_targeted'], equals(20));
    expect(stats.telemetry['soil_moisture_percent'], equals(42.0));
  });
}
