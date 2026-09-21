import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'control_provider.dart';
import '../../app/theme.dart';

class ControlScreen extends ConsumerWidget {
  const ControlScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(controlStateProvider);
    final notifier = ref.read(controlStateProvider.notifier);

    final isBusy = state.isSpraying || state.isIrrigating;

    return Scaffold(
      appBar: AppBar(
        title: const Text('MANUAL CONTROL'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Card(
              color: AppTheme.warning,
              child: Padding(
                padding: EdgeInsets.all(16.0),
                child: Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: Colors.white),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'MANUAL MODE: Direct ESP32 hardware bridge control. Safety authorization active.',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            if (state.statusMessage != null) ...[
              Card(
                color: state.isQueued ? Colors.blue.shade700 : AppTheme.success,
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Row(
                    children: [
                      Icon(state.isQueued ? Icons.schedule : Icons.check_circle, color: Colors.white),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          state.statusMessage!,
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],

            if (state.errorMessage != null) ...[
              Card(
                color: AppTheme.emergency,
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: Colors.white),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          state.errorMessage!,
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],

            if (state.isEmergencyStopped) ...[
              Card(
                color: AppTheme.emergency,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      const Text(
                        'EMERGENCY STOPPED',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 18),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'All pumps isolated. Actuators locked until reset.',
                        style: TextStyle(color: Colors.white70, fontSize: 13),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        onPressed: () => notifier.resetEmergencyStop(),
                        icon: const Icon(Icons.restart_alt),
                        style: ElevatedButton.styleFrom(backgroundColor: Colors.white, foregroundColor: AppTheme.emergency),
                        label: const Text('RESET SYSTEM'),
                      )
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],

            _buildControlSection(
              title: 'Spray Pump Duration: ${state.sprayDuration.toStringAsFixed(1)}s',
              child: Slider(
                value: state.sprayDuration,
                min: 1.0,
                max: 30.0,
                divisions: 29,
                label: '${state.sprayDuration.toStringAsFixed(1)}s',
                onChanged: state.isEmergencyStopped || isBusy ? null : (v) => notifier.setSprayDuration(v),
              ),
            ),
            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: (state.isEmergencyStopped || isBusy) ? null : () => notifier.startSpray(),
                    icon: const Icon(Icons.water_drop),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.moderate,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    label: Text(state.isSpraying ? (state.isQueued ? 'QUEUED...' : 'SPRAYING...') : 'SPRAY PUMP'),
                  ),
                ),
              ],
            ),

            const Divider(height: 48),

            _buildControlSection(
              title: 'Irrigation Solenoid Duration: ${state.irrigationDuration.toStringAsFixed(1)}s',
              child: Slider(
                value: state.irrigationDuration,
                min: 1.0,
                max: 30.0,
                divisions: 29,
                label: '${state.irrigationDuration.toStringAsFixed(1)}s',
                onChanged: state.isEmergencyStopped || isBusy ? null : (v) => notifier.setIrrigationDuration(v),
              ),
            ),
            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: (state.isEmergencyStopped || isBusy) ? null : () => notifier.startIrrigation(),
                    icon: const Icon(Icons.grass),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.teal,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    label: Text(state.isIrrigating ? (state.isQueued ? 'QUEUED...' : 'IRRIGATING...') : 'IRRIGATE PUMP'),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 24),

            ElevatedButton.icon(
              onPressed: isBusy ? () => notifier.stopSpray() : null,
              icon: const Icon(Icons.stop_circle_outlined),
              label: const Text('STOP ALL ACTUATORS'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.offline,
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),

            const SizedBox(height: 32),

            ElevatedButton.icon(
              onPressed: state.isEmergencyStopped ? null : () => notifier.emergencyStop(),
              icon: const Icon(Icons.dangerous),
              label: const Text('EMERGENCY CUTOFF'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.emergency,
                padding: const EdgeInsets.symmetric(vertical: 20),
                textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildControlSection({required String title, required Widget child}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        const SizedBox(height: 8),
        child,
      ],
    );
  }
}
