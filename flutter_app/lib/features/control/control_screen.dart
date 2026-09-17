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
                        'MANUAL MODE: Direct hardware control. Use with caution.',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            if (state.isEmergencyStopped)
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
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: () => notifier.resetEmergencyStop(),
                        style: ElevatedButton.styleFrom(backgroundColor: Colors.white, foregroundColor: AppTheme.emergency),
                        child: const Text('RESET SYSTEM'),
                      )
                    ],
                  ),
                ),
              ),

            const SizedBox(height: 24),



            const SizedBox(height: 24),

            _buildControlSection(
              title: 'Spray Duration: ${state.sprayDuration.toStringAsFixed(1)}s',
              child: Slider(
                value: state.sprayDuration,
                min: 0.1,
                max: 3.0,
                divisions: 29,
                label: '${state.sprayDuration.toStringAsFixed(1)}s',
                onChanged: state.isEmergencyStopped || state.isSpraying ? null : (v) => notifier.setSprayDuration(v),
              ),
            ),

            const SizedBox(height: 48),

            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: (state.isEmergencyStopped || state.isSpraying) ? null : () => notifier.startSpray(),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.moderate,
                      padding: const EdgeInsets.symmetric(vertical: 20),
                    ),
                    child: Text(state.isSpraying ? 'SPRAYING...' : 'SPRAY'),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: ElevatedButton(
                    onPressed: state.isSpraying ? () => notifier.stopSpray() : null,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.offline,
                      padding: const EdgeInsets.symmetric(vertical: 20),
                    ),
                    child: const Text('STOP'),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 48),

            ElevatedButton.icon(
              onPressed: state.isEmergencyStopped ? null : () => notifier.emergencyStop(),
              icon: const Icon(Icons.dangerous),
              label: const Text('EMERGENCY STOP'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.emergency,
                padding: const EdgeInsets.symmetric(vertical: 24),
                textStyle: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
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
