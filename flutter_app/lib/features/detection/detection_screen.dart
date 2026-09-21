import 'dart:io';
import 'package:flutter/foundation.dart';
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
  String? _selectedDemoScenario;

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
        notifier.startScan(imageFile: File(file.path), demoScenario: _selectedDemoScenario);
      } catch (e) {
        debugPrint('Failed to capture image: $e');
        notifier.startScan(demoScenario: _selectedDemoScenario); // fallback
      }
    } else {
      notifier.startScan(demoScenario: _selectedDemoScenario); // fallback
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(detectionStateProvider);
    final notifier = ref.read(detectionStateProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('DETECT (ASSISTED)'),
            if (kDebugMode && _selectedDemoScenario != null)
              Text(
                'Demo: $_selectedDemoScenario',
                style: const TextStyle(fontSize: 10, color: AppTheme.primaryLight),
              ),
          ],
        ),
        actions: [
          if (kDebugMode)
            PopupMenuButton<String?>(
              icon: const Icon(Icons.science_outlined),
              tooltip: 'Demo Scenarios',
              onSelected: (val) {
                setState(() {
                  _selectedDemoScenario = val;
                });
              },
              itemBuilder: (context) => [
                const PopupMenuItem(
                  value: null,
                  child: Text('Live AI (Default)'),
                ),
                const PopupMenuItem(
                  value: 'TOMATO_EARLY_BLIGHT',
                  child: Text('TOMATO_EARLY_BLIGHT (Spray)'),
                ),
                const PopupMenuItem(
                  value: 'DISEASE_HEAVY_RAIN',
                  child: Text('DISEASE_HEAVY_RAIN (Delay)'),
                ),
                const PopupMenuItem(
                  value: 'HEALTHY',
                  child: Text('HEALTHY (Monitor)'),
                ),
                const PopupMenuItem(
                  value: 'LOW_MOISTURE_HEAT',
                  child: Text('LOW_MOISTURE_HEAT (Irrigate)'),
                ),
                const PopupMenuItem(
                  value: 'LOW_CONFIDENCE',
                  child: Text('LOW_CONFIDENCE (Warn)'),
                ),
              ],
            ),
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

    final climateRisk = data['climate_risk'] is Map ? data['climate_risk'] as Map : {};
    final rainRisk = (climateRisk['rain'] ?? climateRisk['heavy_rain']) as num?;
    final heatRisk = climateRisk['heat'] as num?;
    final explanation = data['explanation'] as String?;
    final recommendations = data['recommendations'] is List ? data['recommendations'] as List : [];
    final autoPermitted = decision['auto_permitted'] == true;
    final warnings = decision['warnings'] is List ? decision['warnings'] as List : [];

    return Column(
      children: [
        Card(
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
        ),
        const SizedBox(height: 12),
        // WHY THIS ACTION? Explanation Card
        Card(
          color: Colors.blueGrey.shade50,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: Colors.blueGrey.shade200),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.psychology_alt_outlined, color: Colors.blueGrey.shade800, size: 22),
                    const SizedBox(width: 8),
                    Text(
                      'WHY THIS ACTION?',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                        color: Colors.blueGrey.shade900,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // Decision & Risk Level
                Row(
                  children: [
                    Text('Decision: ', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.blueGrey.shade800)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryLight,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        decision['recommendation'] ?? 'MONITOR',
                        style: const TextStyle(color: AppTheme.primaryDark, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text('Risk: ', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.blueGrey.shade800)),
                    Text(
                      decision['risk_level'] ?? 'LOW',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: decision['risk_level'] == 'HIGH' ? AppTheme.emergency : Colors.black87,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                // Safety Gate Status
                Row(
                  children: [
                    Icon(
                      autoPermitted ? Icons.check_circle_outline : Icons.shield_outlined,
                      size: 16,
                      color: autoPermitted ? AppTheme.success : AppTheme.warning,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      autoPermitted ? 'Safety Gate: Authorized' : 'Safety Gate: Review / Not Permitted',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: autoPermitted ? AppTheme.success : AppTheme.warning,
                      ),
                    ),
                  ],
                ),
                // Climate factors if evaluated
                if (rainRisk != null || heatRisk != null) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: [
                      if (rainRisk != null)
                        Text(
                          'Rain Risk: ${(rainRisk * 100).toStringAsFixed(0)}%',
                          style: TextStyle(
                            fontSize: 11,
                            color: rainRisk >= 0.65 ? AppTheme.warning : Colors.grey.shade700,
                            fontWeight: rainRisk >= 0.65 ? FontWeight.bold : FontWeight.normal,
                          ),
                        ),
                      if (heatRisk != null)
                        Text(
                          'Heat Risk: ${(heatRisk * 100).toStringAsFixed(0)}%',
                          style: TextStyle(
                            fontSize: 11,
                            color: heatRisk >= 0.7 ? AppTheme.emergency : Colors.grey.shade700,
                            fontWeight: heatRisk >= 0.7 ? FontWeight.bold : FontWeight.normal,
                          ),
                        ),
                    ],
                  ),
                ],
                // Farmer Explanation
                if (explanation != null && explanation.isNotEmpty) ...[
                  const Divider(height: 16),
                  Text(
                    explanation,
                    style: const TextStyle(fontSize: 13, height: 1.4, color: Colors.black87),
                  ),
                ],
                // Warnings if any
                if (warnings.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  ...warnings.map((w) => Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.warning_amber_rounded, size: 14, color: AppTheme.warning),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            w.toString(),
                            style: const TextStyle(fontSize: 11, color: AppTheme.warning, fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ),
                  )),
                ],
                // Treatment Recommendations
                if (recommendations.isNotEmpty) ...[
                  const Divider(height: 16),
                  Text('Recommendations:', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.blueGrey.shade800)),
                  const SizedBox(height: 4),
                  ...recommendations.map((r) => Padding(
                    padding: const EdgeInsets.only(left: 4, top: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ', style: TextStyle(fontSize: 12)),
                        Expanded(child: Text(r.toString(), style: const TextStyle(fontSize: 12))),
                      ],
                    ),
                  )),
                ],
              ],
            ),
          ),
        ),
      ],
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
