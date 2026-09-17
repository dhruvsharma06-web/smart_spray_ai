import 'package:flutter/material.dart';
import '../../app/theme.dart';

enum DeviceState { online, offline, ready, busy, error, connected, disconnected }

class StatusBadge extends StatelessWidget {
  final String label;
  final String value;
  final DeviceState state;

  const StatusBadge({
    super.key,
    required this.label,
    required this.value,
    required this.state,
  });

  Color _getColor() {
    switch (state) {
      case DeviceState.online:
      case DeviceState.ready:
      case DeviceState.connected:
        return AppTheme.success;
      case DeviceState.offline:
      case DeviceState.disconnected:
        return AppTheme.offline;
      case DeviceState.busy:
        return AppTheme.info;
      case DeviceState.error:
        return AppTheme.error;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _getColor();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  value.toUpperCase(),
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: color,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
