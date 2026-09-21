import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/config/api_config.dart';
import '../services/api_service.dart';

class NotificationItem {
  final String id;
  final String? deviceId;
  final String? fieldId;
  final DateTime timestamp;
  final String type;
  final String severity;
  final String title;
  final String message;
  final String source;
  final bool isRead;
  final String? decisionId;
  final String? actionId;
  final Map<String, dynamic> stats;

  NotificationItem({
    required this.id,
    this.deviceId,
    this.fieldId,
    required this.timestamp,
    required this.type,
    required this.severity,
    required this.title,
    required this.message,
    required this.source,
    required this.isRead,
    this.decisionId,
    this.actionId,
    required this.stats,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    DateTime parsedTs;
    try {
      parsedTs = DateTime.parse(json['timestamp'] ?? '');
    } catch (_) {
      parsedTs = DateTime.now();
    }

    return NotificationItem(
      id: json['id'] ?? '',
      deviceId: json['device_id'],
      fieldId: json['field_id'],
      timestamp: parsedTs,
      type: json['type'] ?? 'INFO',
      severity: (json['severity'] ?? 'INFO').toString().toUpperCase(),
      title: json['title'] ?? '',
      message: json['message'] ?? '',
      source: json['source'] ?? 'SYSTEM',
      isRead: json['is_read'] == true,
      decisionId: json['decision_id'],
      actionId: json['action_id'],
      stats: json['stats'] is Map<String, dynamic>
          ? json['stats'] as Map<String, dynamic>
          : (json['stats'] is Map ? Map<String, dynamic>.from(json['stats']) : {}),
    );
  }
}

abstract class NotificationRepository {
  Future<List<NotificationItem>> getNotifications({
    String? fieldId,
    String? deviceId,
    bool unreadOnly = false,
    int limit = 50,
  });
  Future<List<NotificationItem>> getActiveNotifications({
    String? fieldId,
    String? deviceId,
    int limit = 10,
  });
  Future<void> markAsRead(String notificationId);
}

class NotificationRepositoryImpl implements NotificationRepository {
  final ApiService _api;

  NotificationRepositoryImpl(this._api);

  @override
  Future<List<NotificationItem>> getNotifications({
    String? fieldId,
    String? deviceId,
    bool unreadOnly = false,
    int limit = 50,
  }) async {
    try {
      final params = <String, dynamic>{
        'unread_only': unreadOnly,
        'limit': limit,
      };
      if (fieldId != null) params['field_id'] = fieldId;
      if (deviceId != null) params['device_id'] = deviceId;

      final res = await _api.get(
        ApiConfig.notifications,
        queryParameters: params,
      );
      final List data = res.data is List ? res.data : [];
      return data.map((e) => NotificationItem.fromJson(Map<String, dynamic>.from(e))).toList();
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<List<NotificationItem>> getActiveNotifications({
    String? fieldId,
    String? deviceId,
    int limit = 10,
  }) async {
    try {
      final params = <String, dynamic>{
        'limit': limit,
      };
      if (fieldId != null) params['field_id'] = fieldId;
      if (deviceId != null) params['device_id'] = deviceId;

      final res = await _api.get(
        '${ApiConfig.notifications}/active',
        queryParameters: params,
      );
      final List data = res.data is List ? res.data : [];
      return data.map((e) => NotificationItem.fromJson(Map<String, dynamic>.from(e))).toList();
    } catch (e) {
      rethrow;
    }
  }

  @override
  Future<void> markAsRead(String notificationId) async {
    try {
      await _api.post('${ApiConfig.notifications}/$notificationId/read');
    } catch (e) {
      rethrow;
    }
  }
}

final notificationRepositoryProvider = Provider<NotificationRepository>((ref) {
  final api = ref.read(apiServiceProvider);
  return NotificationRepositoryImpl(api);
});

// Periodic poller for active notifications (every 5 seconds)
final activeNotificationsProvider = StreamProvider.autoDispose<List<NotificationItem>>((ref) async* {
  final repo = ref.read(notificationRepositoryProvider);
  while (true) {
    try {
      final items = await repo.getActiveNotifications();
      yield items;
    } catch (_) {
      yield [];
    }
    await Future.delayed(const Duration(seconds: 5));
  }
});

// Unread count derived from active notifications
final unreadNotificationCountProvider = Provider.autoDispose<int>((ref) {
  final activeAsync = ref.watch(activeNotificationsProvider);
  return activeAsync.value?.length ?? 0;
});
