"""
Phase 2C YOLOv8n-cls Pest Baseline Training Script.
Trains a lightweight classification baseline on the verified 5-class pest dataset.
Saves weights to ai/models/pest/weights/best.pt and logs evaluation metrics.
"""

import json
import time
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "ai" / "data" / "dataset_pest"
WEIGHTS_DIR = PROJECT_ROOT / "ai" / "models" / "pest" / "weights"


def train():
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=== STARTING PHASE 2C YOLOV8N-CLS PEST BASELINE TRAINING ===")
    print(f"Dataset path: {DATASET_DIR.resolve()}")

    start_time = time.time()

    # Load pretrained YOLOv8n classification model
    model = YOLO("yolov8n-cls.pt")

    # Train on dataset
    results = model.train(
        data=str(DATASET_DIR.resolve()),
        epochs=15,
        imgsz=224,
        batch=16,
        project=str((PROJECT_ROOT / "ai" / "models" / "pest" / "runs").resolve()),
        name="baseline_pest_cls",
        exist_ok=True,
        verbose=True,
    )

    elapsed_seconds = round(time.time() - start_time, 2)
    print(f"\n=== PEST TRAINING COMPLETE IN {elapsed_seconds} SECONDS ===")

    trained_best = Path(results.save_dir) / "weights" / "best.pt"
    target_best = WEIGHTS_DIR / "best.pt"

    if trained_best.exists():
        import shutil
        shutil.copy(trained_best, target_best)
        print(f"Saved best pest weights to: {target_best.resolve()}")
    else:
        print(f"Warning: Trained pest weights file not found at {trained_best}")

    # Evaluate on validation dataset
    metrics = model.val()

    eval_data = {
        "training_time_seconds": elapsed_seconds,
        "epochs": 15,
        "model_architecture": "yolov8n-cls",
        "top1_accuracy": round(float(metrics.top1), 4) if hasattr(metrics, "top1") else None,
        "top5_accuracy": round(float(metrics.top5), 4) if hasattr(metrics, "top5") else None,
        "save_dir": str(results.save_dir),
        "target_weights": str(target_best.resolve()),
    }

    metrics_file = WEIGHTS_DIR / "evaluation_metrics.json"
    metrics_file.write_text(json.dumps(eval_data, indent=2))
    print(f"Pest evaluation metrics written to: {metrics_file.resolve()}")
    print("=== PEST METRICS SUMMARY ===")
    print(json.dumps(eval_data, indent=2))


if __name__ == "__main__":
    train()
