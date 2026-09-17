import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../widgets/status_badge.dart';
import '../../widgets/stat_card.dart';
import '../../app/theme.dart';
import '../../repositories/device_repository.dart';
import '../../repositories/ai_repository.dart';

final deviceStatusProvider = FutureProvider((ref) {
  return ref.read(deviceRepositoryProvider).getDeviceStatus('device-001');
});
final aiStatusProvider = FutureProvider((ref) {
  return ref.read(aiRepositoryProvider).getAiStatus();
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final devAsync = ref.watch(deviceStatusProvider);
    final aiAsync = ref.watch(aiStatusProvider);

    final devStatus = devAsync.value?['status'] ?? 'OFFLINE';
    final pumpStatus = devAsync.value?['pump_status'] ?? 'OFF';
    final aiStatusRaw = aiAsync.value?['data']?['ready'] == true ? 'READY' : 'UNAVAILABLE';

    // We omit fabricating statistics. Wait for an endpoint or show unavailable.

    return Scaffold(
      appBar: AppBar(
        title: const Text('SMARTSPRAY'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'System Status',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                StatusBadge(label: 'Device', value: devStatus.toUpperCase(), state: devStatus == 'offline' ? DeviceState.offline : DeviceState.online),
                StatusBadge(label: 'AI', value: aiStatusRaw, state: aiStatusRaw == 'READY' ? DeviceState.ready : DeviceState.offline),
                StatusBadge(label: 'ESP32', value: devAsync.value?['esp32_connected'] == true ? 'CONNECTED' : 'DISCONNECTED', state: devAsync.value?['esp32_connected'] == true ? DeviceState.connected : DeviceState.offline),
                StatusBadge(label: 'Pump', value: pumpStatus.toUpperCase(), state: pumpStatus == 'on' ? DeviceState.ready : DeviceState.offline),
              ],
            ),
            const SizedBox(height: 32),
            const Text(
              'Today\'s Statistics',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            const Row(
              children: [
                Expanded(child: StatCard(label: 'Plants Scanned', value: '--')),
                SizedBox(width: 16),
                Expanded(child: StatCard(label: 'Infected', value: '--')),
                SizedBox(width: 16),
                Expanded(child: StatCard(label: 'Sprayed', value: '--')),
              ],
            ),
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
                    'Operating Mode: ${devAsync.value?["mode"] ?? "ASSISTED"}',
                    style: const TextStyle(
                      color: AppTheme.primaryDark,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'AI detects disease and recommends spray. Operator confirms.',
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
}
