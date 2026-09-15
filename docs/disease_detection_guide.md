# SMART SPRAY — Disease Detection & Training Guide (Phase 2B Update)

This document details the architectural foundation, verified dataset ingestion, model training, evaluation metrics, and operational procedures for crop disease detection in the SMART SPRAY AI/ML module.

---

## 1. Verified Dataset Structure & Counts

For Phase 2B training, we prepared a verified 6-class dataset sourced from **PlantDoc** and **PlantVillage**:
- **Tomato Healthy**: Sourced from PlantDoc (`train/Tomato leaf`).
- **Tomato Early Blight**: Sourced from PlantDoc (`train/Tomato Early blight leaf`).
- **Tomato Late Blight**: Sourced from PlantDoc (`train/Tomato leaf late blight`).
- **Potato Early Blight**: Sourced from PlantDoc (`train/Potato leaf early blight`).
- **Potato Late Blight**: Sourced from PlantDoc (`train/Potato leaf late blight`).
- **Potato Healthy**: Sourced from PlantVillage (`raw/color/Potato___healthy`) to ensure genuine potato foliage images without mislabeling tomato foliage.

Every image file was verified using `PIL.Image.open().verify()`. Unreadable or missing files were automatically discarded.

| Class Name | Source Repo | Train Images | Val Images | Total Verified Images |
|---|---|---|---|---|
| `tomato_early_blight` | PlantDoc | 60 | 12 | **72** |
| `tomato_late_blight` | PlantDoc | 75 | 19 | **94** |
| `tomato_healthy` | PlantDoc | 43 | 10 | **53** |
| `potato_early_blight` | PlantDoc | 79 | 21 | **100** |
| `potato_late_blight` | PlantDoc | 77 | 19 | **96** |
| `potato_healthy` | PlantVillage | 44 | 11 | **55** |
| **GRAND TOTAL** | | **378** | **92** | **470** |

---

## 2. Baseline Model Training & Architecture

- **Model**: `yolov8n-cls` (classification baseline)
- **Pretrained Weights**: `yolov8n-cls.pt` (ImageNet pretrained backbone)
- **Image Resolution**: 224x224
- **Epochs**: 25
- **Batch Size**: 16
- **Training Duration**: 550.29 seconds (~9 minutes)

### Training Evaluation Metrics
- **Top-1 Accuracy**: **72.83%** (`0.7283`)
- **Top-5 Accuracy**: **100.0%** (`1.0`)
- **Saved Weights Location**: `ai/models/disease/weights/best.pt`
- **Evaluation Metrics JSON**: `ai/models/disease/weights/evaluation_metrics.json`

> [!NOTE]
> `yolov8n-cls` is a classification baseline. It outputs disease identity, probabilities, and confidence tiers, but does not provide bounding-box spatial localization or lesion segmentation. Lesion localization will be added in subsequent object-detection / segmentation phases.

---

## 3. Real Inference & Adapter Integration

Trained weights are loaded automatically via `DiseaseModelAdapter`:

```python
from ai.models.disease import DiseaseModelAdapter

# Initialize adapter with trained weights
adapter = DiseaseModelAdapter(weights_path="ai/models/disease/weights/best.pt")

# Perform inference on leaf image
result = adapter.detect("ai/data/sample_images/sample_tomato_early_blight.jpg", crop="tomato")

print(f"Diagnosed Disease: {result.disease}")
print(f"Confidence: {result.confidence:.4f} ({result.confidence_level})")
print(f"Requires Confirmation: {result.requires_confirmation}")
```

### Real Model Output JSON Contract
```json
{
  "disease": "early_blight",
  "display_name": "Early Blight",
  "confidence": 0.6863,
  "crop": "potato",
  "is_healthy": false,
  "confidence_level": "moderate",
  "requires_confirmation": true,
  "detections": [],
  "affected_area_percent": null,
  "symptoms": [
    "Concentric circular lesions, foliar necrosis"
  ]
}
```

---

## 4. Test Suite Verification

Pytest execution confirms 100% test pass rate across Phase 1, Phase 2A, and Phase 2B:
```bash
python -m pytest tests/ -v
```
**Results**: `26 passed, 1 skipped` (including `test_real_model_adapter_trained_inference`).
