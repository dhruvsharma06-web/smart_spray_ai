"""
Phase 2B Dataset Download Script.
Downloads curated PlantDoc subset from pratikkayal/PlantDoc-Dataset for:
  - Tomato: Early Blight, Late Blight, Healthy
  - Potato: Early Blight, Late Blight (Healthy sourced from Tomato healthy folder)

6 classes, ~496 images total.
Creates proper 80/20 train/val split in YOLO-cls directory format.
"""

import json
import os
import random
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "pratikkayal/PlantDoc-Dataset"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DATASET_DIR = Path("ai/data/dataset_disease")
SEED = 42
SPLIT_RATIO = 0.80

# 6 classes: PlantDoc folder → local class name
SOURCES = [
    ("train/Tomato Early blight leaf",  "tomato_early_blight"),
    ("train/Tomato leaf late blight",   "tomato_late_blight"),
    ("train/Tomato leaf",               "tomato_healthy"),
    ("train/Potato leaf early blight",  "potato_early_blight"),
    ("train/Potato leaf late blight",   "potato_late_blight"),
    ("train/Tomato leaf",               "potato_healthy"),   # No separate healthy potato folder in PlantDoc
]


def fetch_file_list(rel_path: str):
    url = f"https://api.github.com/repos/{REPO}/contents/{urllib.parse.quote(rel_path)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read().decode())
    return [i for i in items if i["name"].lower().endswith((".jpg", ".jpeg", ".png"))]


def download_image(download_url: str, dest: Path):
    req = urllib.request.Request(download_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.read())


def main():
    random.seed(SEED)

    # Clean and recreate dataset directory
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)

    # Create split dirs
    for split in ("train", "val"):
        for _, cls in SOURCES:
            (DATASET_DIR / split / cls).mkdir(parents=True, exist_ok=True)

    summary = {}

    for rel_path, cls_name in SOURCES:
        print(f"\nFetching file list: {rel_path} → {cls_name}")
        items = fetch_file_list(rel_path)

        # Shuffle deterministically
        random.shuffle(items)
        n_train = int(len(items) * SPLIT_RATIO)
        splits = {"train": items[:n_train], "val": items[n_train:]}

        for split_name, split_items in splits.items():
            for item in split_items:
                # Use class-prefixed filename to avoid collisions between shared sources
                dest_name = f"{cls_name}_{item['name']}"
                dest = DATASET_DIR / split_name / cls_name / dest_name
                if not dest.exists():
                    download_image(item["download_url"], dest)

            print(f"  {split_name}: {len(split_items)} images → {DATASET_DIR / split_name / cls_name}")

        summary[cls_name] = {"total": len(items), "train": n_train, "val": len(items) - n_train}

    # Write summary JSON
    summary_path = DATASET_DIR / "dataset_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print("\n=== DATASET SUMMARY ===")
    grand_total = 0
    for cls, counts in summary.items():
        grand_total += counts["total"]
        print(f"  {cls}: {counts['total']} total  ({counts['train']} train / {counts['val']} val)")
    print(f"  GRAND TOTAL: {grand_total} images")
    print(f"\nDataset written to: {DATASET_DIR.resolve()}")


if __name__ == "__main__":
    main()
