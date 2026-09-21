import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'history_provider.dart';
import '../../app/theme.dart';

class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(historyStateProvider);
    final notifier = ref.read(historyStateProvider.notifier);
    final events = state.filteredEvents;

    return Scaffold(
      appBar: AppBar(
        title: const Text('HISTORY'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () => notifier.loadEvents())
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: Container(
            color: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: HistoryFilter.values.map((filter) {
                  final isSelected = state.filter == filter;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8.0),
                    child: ChoiceChip(
                      label: Text(filter.name.toUpperCase()),
                      selected: isSelected,
                      onSelected: (selected) {
                        if (selected) notifier.setFilter(filter);
                      },
                      selectedColor: AppTheme.primaryLight,
                      labelStyle: TextStyle(
                        color: isSelected ? AppTheme.primaryDark : AppTheme.secondaryText,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ),
      ),
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : state.error != null
              ? Center(child: Text("Error: ${state.error}"))
              : events.isEmpty
                  ? const Center(child: Text('No events found.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16.0),
                      itemCount: events.length,
                      itemBuilder: (context, index) {
                        final event = events[index];
                        return _buildEventCard(context, event);
                      },
                    ),
    );
  }

  Widget _buildEventCard(BuildContext context, dynamic event) {
    String status = (event['status'] ?? 'unknown').toString().toLowerCase();
    Color statusColor = AppTheme.secondaryText;
    if (status == 'completed') statusColor = AppTheme.success;
    if (status == 'started') statusColor = Colors.blue;
    if (status == 'queued') statusColor = AppTheme.warning;
    if (status == 'failed' || status == 'stopped' || status == 'error' || status == 'blocked') statusColor = AppTheme.error;
    if (status == 'skipped') statusColor = AppTheme.info;

    DateTime? ts;
    try {
      ts = DateTime.parse(event['started_at'] ?? event['timestamp'] ?? '');
    } catch (_) { }

    final plantsTargeted = event['plants_targeted'];
    final disease = event['disease'] as String?;
    final severity = event['severity'] as String?;
    final reason = event['reason'] as String?;
    final ackState = event['ack_state'] as String?;
    final durationMs = (event['duration_ms'] ?? 0) as int;
    final durationSec = durationMs > 0 ? (durationMs / 1000).toStringAsFixed(1) : '0';

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  ts != null ? DateFormat('HH:mm - MMM d, yyyy').format(ts.toLocal()) : 'Unknown Time',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.bold),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    status.toUpperCase(),
                    style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const Divider(),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  event['action'] ?? event['mode'] ?? 'Unknown',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                Text(
                  durationMs >= 1000 ? '${durationSec}s duration' : '${durationMs}ms duration',
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
              ],
            ),
            if (disease != null || plantsTargeted != null || severity != null) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  if (plantsTargeted != null)
                    Chip(
                      label: Text('$plantsTargeted plants targeted'),
                      backgroundColor: AppTheme.primaryLight.withValues(alpha: 0.5),
                      labelStyle: const TextStyle(fontSize: 11, color: AppTheme.primaryDark),
                      padding: EdgeInsets.zero,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  if (disease != null && disease.toLowerCase() != 'healthy')
                    Chip(
                      label: Text(disease.replaceAll('_', ' ')),
                      backgroundColor: Colors.red.shade50,
                      labelStyle: TextStyle(fontSize: 11, color: Colors.red.shade800),
                      padding: EdgeInsets.zero,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  if (severity != null)
                    Chip(
                      label: Text('Severity: $severity'),
                      backgroundColor: Colors.amber.shade50,
                      labelStyle: TextStyle(fontSize: 11, color: Colors.amber.shade900),
                      padding: EdgeInsets.zero,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                ],
              ),
            ],
            if (reason != null && reason.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                reason,
                style: TextStyle(fontSize: 12, color: Colors.grey.shade800),
              ),
            ],
            if (event['error_message'] != null) ...[
              const SizedBox(height: 4),
              Text(
                'Rejection: ${event['error_message']}',
                style: const TextStyle(color: AppTheme.error, fontSize: 12, fontWeight: FontWeight.bold),
              ),
            ],
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                if (ackState != null)
                  Text(
                    'ESP32 ACK: $ackState',
                    style: TextStyle(
                      fontSize: 11,
                      color: ackState == 'COMPLETED' ? AppTheme.success : Colors.blueGrey,
                      fontWeight: FontWeight.w600,
                    ),
                  )
                else
                  const SizedBox.shrink(),
                if (event['command_id'] != null)
                  Text('ID: ${event['command_id']}', style: Theme.of(context).textTheme.labelSmall),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
