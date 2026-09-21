import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../app/theme.dart';
import '../../repositories/notification_repository.dart';

final notificationsListProvider = FutureProvider.autoDispose.family<List<NotificationItem>, bool>((ref, unreadOnly) async {
  final repo = ref.read(notificationRepositoryProvider);
  return await repo.getNotifications(unreadOnly: unreadOnly);
});

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  bool _unreadOnly = false;

  IconData _getCategoryIcon(String type) {
    switch (type.toUpperCase()) {
      case 'HEATWAVE':
        return Icons.wb_sunny;
      case 'HEAVY_RAIN':
        return Icons.water_drop;
      case 'FLOOD_WATERLOGGING':
        return Icons.flood;
      case 'DISEASE_DETECTED':
        return Icons.bug_report;
      case 'SPRAY_QUEUED':
      case 'SPRAY_STARTED':
      case 'SPRAY_COMPLETED':
        return Icons.shower;
      case 'IRRIGATION_QUEUED':
      case 'IRRIGATION_STARTED':
      case 'IRRIGATION_COMPLETED':
        return Icons.opacity;
      case 'SPRAY_DELAYED':
      case 'IRRIGATION_DELAYED':
        return Icons.schedule;
      case 'SPRAY_BLOCKED':
      case 'IRRIGATION_BLOCKED':
        return Icons.block;
      default:
        return Icons.notifications;
    }
  }

  Color _getSeverityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return AppTheme.emergency;
      case 'HIGH':
        return AppTheme.moderate;
      case 'MEDIUM':
        return AppTheme.warning;
      case 'INFO':
      default:
        return AppTheme.info;
    }
  }

  Future<void> _markRead(String notifId) async {
    try {
      await ref.read(notificationRepositoryProvider).markAsRead(notifId);
      ref.invalidate(notificationsListProvider);
      ref.invalidate(activeNotificationsProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to mark as read: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final notifsAsync = ref.watch(notificationsListProvider(_unreadOnly));

    return Scaffold(
      appBar: AppBar(
        title: const Text('NOTIFICATIONS & ALERTS'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(notificationsListProvider),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: Container(
            color: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                ChoiceChip(
                  label: const Text('ALL'),
                  selected: !_unreadOnly,
                  onSelected: (val) {
                    if (val) setState(() => _unreadOnly = false);
                  },
                  selectedColor: AppTheme.primaryLight,
                  labelStyle: TextStyle(
                    color: !_unreadOnly ? AppTheme.primaryDark : AppTheme.secondaryText,
                    fontWeight: !_unreadOnly ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
                const SizedBox(width: 8),
                ChoiceChip(
                  label: const Text('UNREAD ONLY'),
                  selected: _unreadOnly,
                  onSelected: (val) {
                    if (val) setState(() => _unreadOnly = true);
                  },
                  selectedColor: AppTheme.primaryLight,
                  labelStyle: TextStyle(
                    color: _unreadOnly ? AppTheme.primaryDark : AppTheme.secondaryText,
                    fontWeight: _unreadOnly ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      body: notifsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) => Center(child: Text('Error: $err')),
        data: (items) {
          if (items.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.notifications_off_outlined, size: 64, color: Colors.grey.shade400),
                  const SizedBox(height: 16),
                  Text(
                    _unreadOnly ? 'No unread notifications' : 'No notifications found',
                    style: const TextStyle(fontSize: 16, color: AppTheme.secondaryText),
                  ),
                ],
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(notificationsListProvider),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: items.length,
              itemBuilder: (context, index) {
                final item = items[index];
                final sevColor = _getSeverityColor(item.severity);
                final catIcon = _getCategoryIcon(item.type);

                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  elevation: item.isRead ? 1 : 3,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                      color: item.isRead ? Colors.grey.shade200 : sevColor.withValues(alpha: 0.5),
                      width: item.isRead ? 1 : 1.5,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: sevColor.withValues(alpha: 0.1),
                                shape: BoxShape.circle,
                              ),
                              child: Icon(catIcon, color: sevColor, size: 22),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Expanded(
                                        child: Text(
                                          item.title,
                                          style: TextStyle(
                                            fontWeight: item.isRead ? FontWeight.w600 : FontWeight.bold,
                                            fontSize: 15,
                                          ),
                                        ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: sevColor.withValues(alpha: 0.15),
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Text(
                                          item.severity,
                                          style: TextStyle(
                                            color: sevColor,
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    DateFormat('HH:mm · MMM d, yyyy').format(item.timestamp.toLocal()),
                                    style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          item.message,
                          style: TextStyle(
                            fontSize: 13,
                            color: item.isRead ? Colors.black87 : Colors.black,
                            fontWeight: item.isRead ? FontWeight.normal : FontWeight.w500,
                          ),
                        ),
                        if (item.stats.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 6,
                            runSpacing: 4,
                            children: [
                              if (item.stats['plants_targeted'] != null)
                                Chip(
                                  label: Text('${item.stats['plants_targeted']} plants targeted'),
                                  backgroundColor: AppTheme.primaryLight.withValues(alpha: 0.4),
                                  labelStyle: const TextStyle(fontSize: 11, color: AppTheme.primaryDark),
                                  padding: EdgeInsets.zero,
                                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                              if (item.stats['duration_seconds'] != null)
                                Chip(
                                  label: Text('${item.stats['duration_seconds']}s duration'),
                                  backgroundColor: Colors.grey.shade100,
                                  labelStyle: const TextStyle(fontSize: 11),
                                  padding: EdgeInsets.zero,
                                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                              if (item.stats['temperature_celsius'] != null)
                                Chip(
                                  label: Text('${(item.stats['temperature_celsius'] as num).toStringAsFixed(1)}°C'),
                                  backgroundColor: Colors.red.shade50,
                                  labelStyle: TextStyle(fontSize: 11, color: Colors.red.shade800),
                                  padding: EdgeInsets.zero,
                                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                              if (item.stats['soil_moisture_percent'] != null)
                                Chip(
                                  label: Text('${(item.stats['soil_moisture_percent'] as num).toStringAsFixed(0)}% soil moisture'),
                                  backgroundColor: Colors.blue.shade50,
                                  labelStyle: TextStyle(fontSize: 11, color: Colors.blue.shade800),
                                  padding: EdgeInsets.zero,
                                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                            ],
                          ),
                        ],
                        if (!item.isRead) ...[
                          const SizedBox(height: 8),
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton.icon(
                              onPressed: () => _markRead(item.id),
                              icon: const Icon(Icons.check, size: 16),
                              label: const Text('Mark as Read', style: TextStyle(fontSize: 12)),
                              style: TextButton.styleFrom(
                                visualDensity: VisualDensity.compact,
                                foregroundColor: AppTheme.primaryDark,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
