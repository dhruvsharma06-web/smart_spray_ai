import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import '../features/detection/detection_provider.dart';

class DetectionVisualizer extends StatelessWidget {
  final DetectionState state;
  final CameraController? cameraController;

  const DetectionVisualizer(
      {super.key, required this.state, this.cameraController});

  @override
  Widget build(BuildContext context) {
    if (state.status == DetectionStatus.idle ||
        state.status == DetectionStatus.scanning) {
      if (cameraController != null && cameraController!.value.isInitialized) {
        return ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: AspectRatio(
            aspectRatio: 3 / 4,
            child: CameraPreview(cameraController!),
          ),
        );
      }
      return Container(
        height: 300,
        alignment: Alignment.center,
        color: Colors.grey[200],
        child: const Text('Initializing camera...'),
      );
    }

    // Default view for results or offline
    return Container(
      height: 300,
      alignment: Alignment.center,
      color: Colors.black12,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.image, size: 48, color: Colors.grey),
          const SizedBox(height: 16),
          Text(
            state.status == DetectionStatus.offline
                ? 'Backend API offline'
                : 'Showing result visualization',
            style: TextStyle(color: Colors.grey[600]),
          ),
        ],
      ),
    );
  }
}
