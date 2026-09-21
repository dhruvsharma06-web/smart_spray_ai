import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../widgets/status_badge.dart';
import '../../widgets/stat_card.dart';
import '../../app/theme.dart';
import '../../repositories/device_repository.dart';
import '../../repositories/ai_repository.dart';
import '../../repositories/notification_repository.dart';
import '../../repositories/statistics_repository.dart';

final liveDeviceStatusProvider = StreamProvider.autoDispose<Map<String, dynamic>>((ref) async* {
  final repo = ref.read(deviceRepositoryProvider);
  while (true) {
    try {
      final res = await repo.getDeviceStatus('device-001');
      yield res;
    } catch (e) {
      yield {
        'status': 'OFFLINE',
        'esp32_connected': false,
        'pump_status': 'off',
        'current_action': 'IDLE',
        'error': e.toString(),
      };
    }
    await Future.delayed(const Duration(seconds: 3));
  }
});

final aiStatusProvider = FutureProvider((ref) {
  return ref.read(aiRepositoryProvider).getAiStatus();
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final devAsync = ref.watch(liveDeviceStatusProvider);
    final aiAsync = ref.watch(aiStatusProvider);
    final unreadCount = ref.watch(unreadNotificationCountProvider);
    final activeNotifsAsync = ref.watch(activeNotificationsProvider);
    final statsAsync = ref.watch(liveStatisticsProvider);

    final devData = devAsync.value ?? {};
    final isEspConnected = devData['esp32_connected'] == true;
    final devStatus = isEspConnected
        ? ((devData['status'] as String?)?.toUpperCase() ?? 'ONLINE')
        : 'OFFLINE';
    final pumpStatus = isEspConnected
        ? ((devData['pump_status'] as String?)?.toUpperCase() ?? 'OFF')
        : 'OFF';
    final currentAction = isEspConnected
        ? ((devData['current_action'] as String?)?.toUpperCase() ?? 'IDLE')
        : 'IDLE';
    final aiStatusRaw = aiAsync.value?['data']?['ready'] == true ? 'READY' : 'UNAVAILABLE';

    // Sensor Telemetry Extracted ONLY from Real ESP32 payload when connected
    final soil = (isEspConnected && devData['soil'] is Map) ? devData['soil'] as Map : {};
    final env = (isEspConnected && devData['environment'] is Map) ? devData['environment'] as Map : {};

    final tempVal = (isEspConnected && env['temperature_celsius'] != null)
        ? '${(env['temperature_celsius'] as num).toStringAsFixed(1)}°C'
        : '--';
    final humVal = (isEspConnected && env['humidity_percent'] != null)
        ? '${(env['humidity_percent'] as num).toStringAsFixed(1)}%'
        : '--';
    final soilVal = (isEspConnected && soil['moisture_percent'] != null)
        ? '${soil['moisture_percent']}%'
        : '--';
    final rainVal = (isEspConnected && env['rain_detected'] != null)
        ? (env['rain_detected'] == true ? 'YES' : 'NO')
        : '--';

    // Check for active climate warnings
    final activeNotifs = activeNotifsAsync.value ?? [];
    final climateWarnings = activeNotifs.where((n) =>
        ['HEATWAVE', 'HEAVY_RAIN', 'FLOOD_WATERLOGGING'].contains(n.type)).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('SMARTSPRAY'),
        actions: [
          IconButton(
            tooltip: 'Notifications',
            icon: Badge(
              isLabelVisible: unreadCount > 0,
              label: Text('$unreadCount'),
              child: const Icon(Icons.notifications_outlined),
            ),
            onPressed: () => context.push('/notifications'),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Climate Warning Banner (if any active)
            if (climateWarnings.isNotEmpty) ...[
              _buildClimateWarningBanner(context, climateWarnings.first),
              const SizedBox(height: 16),
            ],

            const Text(
              'Real Hardware Status',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                StatusBadge(
                  label: 'Device',
                  value: devStatus,
                  state: devStatus == 'ONLINE' ? DeviceState.online : DeviceState.offline,
                ),
                StatusBadge(
                  label: 'AI Service',
                  value: aiStatusRaw,
                  state: aiStatusRaw == 'READY' ? DeviceState.ready : DeviceState.offline,
                ),
                StatusBadge(
                  label: 'ESP32 Hardware',
                  value: isEspConnected ? 'CONNECTED' : 'DISCONNECTED',
                  state: isEspConnected ? DeviceState.connected : DeviceState.disconnected,
                ),
                StatusBadge(
                  label: 'Actuator',
                  value: currentAction != 'IDLE' ? currentAction : pumpStatus,
                  state: (pumpStatus == 'ON' || currentAction != 'IDLE') ? DeviceState.ready : DeviceState.offline,
                ),
              ],
            ),
            const SizedBox(height: 32),
            const Text(
              'Live Sensor Telemetry (3s Feed)',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(child: StatCard(label: 'Temp (DHT22)', value: tempVal)),
                const SizedBox(width: 8),
                Expanded(child: StatCard(label: 'Humidity', value: humVal)),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: StatCard(label: 'Soil Moisture', value: soilVal)),
                const SizedBox(width: 8),
                Expanded(child: StatCard(label: 'Rain Sensor', value: rainVal)),
              ],
            ),
            const SizedBox(height: 32),

            // Real Field Statistics Section
            const Text(
              'Field Intelligence & Operations',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            _buildFieldStatisticsSection(context, statsAsync),

            const SizedBox(height: 32),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.primaryLight,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.primary.withValues(alpha: 0.3)),
              ),
              child: Column(
                children: [
                  Text(
                    'Operating Mode: ${devData["mode"] ?? "ASSISTED"}',
                    style: const TextStyle(
                      color: AppTheme.primaryDark,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'AI detects disease & safety gate authorizes actuation pipeline.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppTheme.primaryDark, fontSize: 13),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () {
                      context.go('/detect');
                    },
                    icon: const Icon(Icons.document_scanner),
                    label: const Text('START SCAN'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildClimateWarningBanner(BuildContext context, NotificationItem warning) {
    Color bannerColor = AppTheme.warning;
    IconData bannerIcon = Icons.warning_amber_rounded;
    if (warning.type == 'HEATWAVE') {
      bannerColor = Colors.deepOrange;
      bannerIcon = Icons.wb_sunny_rounded;
    } else if (warning.type == 'HEAVY_RAIN') {
      bannerColor = Colors.blue.shade700;
      bannerIcon = Icons.water_drop_rounded;
    } else if (warning.type == 'FLOOD_WATERLOGGING') {
      bannerColor = Colors.indigo;
      bannerIcon = Icons.flood_rounded;
    }

    return InkWell(
      onTap: () => context.push('/notifications'),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: bannerColor.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: bannerColor, width: 1.5),
        ),
        child: Row(
          children: [
            Icon(bannerIcon, color: bannerColor, size: 28),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        warning.title.toUpperCase(),
                        style: TextStyle(
                          color: bannerColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          color: bannerColor,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          warning.severity,
                          style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    warning.message,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12, color: Colors.black87),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: bannerColor),
          ],
        ),
      ),
    );
  }

  Widget _buildFieldStatisticsSection(BuildContext context, AsyncValue<FieldStatistics> statsAsync) {
    return statsAsync.when(
      loading: () => const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator())),
      error: (err, stack) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Field Intelligence & Operations', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
              const SizedBox(height: 8),
              Text('No field statistics available at this time.', style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
            ],
          ),
        ),
      ),
      data: (stats) {
        final healthColor = stats.healthSummary == 'HEALTHY'
            ? AppTheme.success
            : (stats.healthSummary == 'ATTENTION_NEEDED' ? AppTheme.warning : AppTheme.secondaryText);

        final latestOp = stats.latestOperation;
        String latestOpText = 'None recorded yet';
        if (latestOp != null) {
          final act = latestOp['action'] ?? '';
          final st = latestOp['status'] ?? '';
          final dur = latestOp['duration_seconds'] != null ? '${latestOp['duration_seconds']}s' : '';
          final targeted = latestOp['plants_targeted'] != null ? ' · ${latestOp['plants_targeted']} plants targeted' : '';
          DateTime? ts;
          try {
            ts = DateTime.parse(latestOp['timestamp'] ?? '');
          } catch (_) {}
          final timeStr = ts != null ? DateFormat('HH:mm').format(ts.toLocal()) : '';
          latestOpText = '$act ($st) $dur$targeted at $timeStr'.trim();
        }

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Field Health', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: healthColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        stats.healthSummary.replaceAll('_', ' '),
                        style: TextStyle(color: healthColor, fontSize: 11, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  stats.recentScansCount > 0
                      ? '${stats.recentScansCount} recent scan(s) evaluated by AI'
                      : 'No recent scans',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                ),
                const Divider(height: 24),
                const Text('Operations Summary', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Total Actions', style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                          Text('${stats.totalActions}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Sprays', style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                          Text('${stats.totalSprays}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.primaryDark)),
                        ],
                      ),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Irrigations', style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                          Text('${stats.totalIrrigations}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.blue)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Latest Operation', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.grey.shade700)),
                      const SizedBox(height: 2),
                      Text(latestOpText, style: const TextStyle(fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
