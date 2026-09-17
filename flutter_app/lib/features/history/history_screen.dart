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
    if (status == 'failed' || status == 'stopped' || status == 'error') statusColor = AppTheme.error;
    if (status == 'skipped') statusColor = AppTheme.info;

    DateTime? ts;
    try {
      ts = DateTime.parse(event['started_at'] ?? '');
    } catch (_) { }

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
                  ts != null ? DateFormat('HH:mm - MMM d').format(ts) : 'Unknown Time',
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
                Text(event['mode'] ?? 'Unknown mode', style: const TextStyle(fontWeight: FontWeight.bold)),
                Text('${event['duration_ms'] ?? 0} ms duration'),
              ],
            ),
            const SizedBox(height: 8),
            if (event['error_message'] != null)
              Text('Error: ${event['error_message']}', style: const TextStyle(color: AppTheme.error)),
            if (event['command_id'] != null)
              Text('CMD ID: ${event['command_id']}', style: Theme.of(context).textTheme.labelSmall),
          ],
        ),
      ),
    );
  }
}
