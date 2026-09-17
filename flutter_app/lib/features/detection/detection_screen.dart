import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:camera/camera.dart';
import 'detection_provider.dart';
import '../../widgets/detection_visualizer.dart';
import '../../app/theme.dart';

class DetectionScreen extends ConsumerStatefulWidget {
  const DetectionScreen({super.key});

  @override
  ConsumerState<DetectionScreen> createState() => _DetectionScreenState();
}

class _DetectionScreenState extends ConsumerState<DetectionScreen> {
  CameraController? _cameraController;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isNotEmpty) {
        final rearCamera = cameras.firstWhere(
          (c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => cameras.first,
        );
        _cameraController = CameraController(
          rearCamera,
          ResolutionPreset.medium,
          enableAudio: false,
        );
        await _cameraController!.initialize();
        if (mounted) {
          setState(() {});
        }
      }
    } catch (e) {
      debugPrint('Camera initialization error: $e');
    }
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    super.dispose();
  }

  Future<void> _handleStartScan() async {
    final notifier = ref.read(detectionStateProvider.notifier);

    if (_cameraController != null && _cameraController!.value.isInitialized) {
      try {
        final XFile file = await _cameraController!.takePicture();
        notifier.startScan(imageFile: File(file.path));
      } catch (e) {
        debugPrint('Failed to capture image: $e');
        notifier.startScan(); // fallback
      }
    } else {
      notifier.startScan(); // fallback
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(detectionStateProvider);
    final notifier = ref.read(detectionStateProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('DETECT (ASSISTED)'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => notifier.reset(),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            DetectionVisualizer(
              state: state,
              cameraController: _cameraController,
            ),
            const SizedBox(height: 24),
            _buildStatusPanel(state),
            const SizedBox(height: 24),
            _buildControls(context, state, notifier),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusPanel(DetectionState state) {
    if (state.status == DetectionStatus.idle) {
      return const Center(child: Text('Press START SCAN to begin.'));
    }

    if (state.status == DetectionStatus.scanning) {
      return const Center(
        child: Column(
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Looking for a plant...'),
          ],
        ),
      );
    }

    if (state.status == DetectionStatus.error ||
        state.status == DetectionStatus.offline) {
      return Center(
        child: Text(state.errorMessage ?? 'Error occurred.',
            style: const TextStyle(
                color: AppTheme.error, fontWeight: FontWeight.bold)),
      );
    }

    final data = state.aiResult?['data'];
    final decision = state.aiResult?['decision'];

    if (data == null || decision == null) return const SizedBox.shrink();

    final disease = data['disease'] ?? 'healthy';
    final isUncertain = data['uncertain'] == true;
    final leaf = data['leaf'];
    final lesion = data['lesion'];
    final severity = data['severity'];

    if (isUncertain) {
      return Card(
          color: AppTheme.warning,
          child: const Padding(
            padding: EdgeInsets.all(16),
            child: Text('AI RESULT UNCERTAIN',
                style: TextStyle(
                    color: Colors.white, fontWeight: FontWeight.bold)),
          ));
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (leaf != null && leaf['detected'] == true)
              const _StatusRow(
                  icon: Icons.spa, text: 'Leaf detected', color: Colors.blue),
            const Divider(),
            if (disease != 'healthy') ...[
              Text('Disease: ${disease.replaceAll("_", " ")}',
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 16)),
              if (lesion != null && lesion['confidence'] != null)
                Text(
                    'Confidence: ${(lesion['confidence'] * 100).toStringAsFixed(1)}%'),
            ] else ...[
              const Text('Healthy Plant',
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: AppTheme.success)),
            ],
            if (severity != null) ...[
              const Divider(),
              Text(
                  'Severity: ${severity['percentage']?.toStringAsFixed(1) ?? '0'}%',
                  style: const TextStyle(
                      color: AppTheme.moderate, fontWeight: FontWeight.bold)),
              Text('Severity Level: ${severity['level']}',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
            ],
            const Divider(),
            Text(
              'Recommended: ${decision['recommendation']}',
              style: TextStyle(
                  color: decision['recommendation'] == 'NO_SPRAY'
                      ? AppTheme.text
                      : AppTheme.emergency,
                  fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildControls(BuildContext context, DetectionState state,
      DetectionStateNotifier notifier) {
    if (state.status == DetectionStatus.idle) {
      return ElevatedButton.icon(
        onPressed: _handleStartScan,
        icon: const Icon(Icons.document_scanner),
        label: const Text('START SCAN'),
      );
    }

    if (state.status == DetectionStatus.resultReady) {
      final decision = state.aiResult?['decision'];
      final canSpray = decision != null &&
          decision['recommendation'] != 'NO_SPRAY' &&
          decision['auto_permitted'] == true;

      return Row(
        children: [
          Expanded(
            child: OutlinedButton(
              onPressed: () => notifier.skip(),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(double.infinity, 48),
              ),
              child: const Text('SKIP'),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            flex: 2,
            child: ElevatedButton(
              onPressed: canSpray ? () => notifier.spray() : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.moderate,
              ),
              child: const Text('SPRAY'),
            ),
          ),
        ],
      );
    }

    if (state.status == DetectionStatus.spraying) {
      return ElevatedButton(
        onPressed: null,
        style: ElevatedButton.styleFrom(
          disabledBackgroundColor: AppTheme.moderate.withValues(alpha: 0.5),
        ),
        child: const Text('SPRAYING...'),
      );
    }

    return const SizedBox.shrink();
  }
}

class _StatusRow extends StatelessWidget {
  final IconData icon;
  final String text;
  final Color color;

  const _StatusRow(
      {required this.icon, required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Text(text),
        ],
      ),
    );
  }
}
