"""
Phase 2B Dataset Preparation Script (Multi-Threaded).
Downloads verified disease dataset:
- PlantDoc (441 images across 5 classes)
- PlantVillage (55 genuine potato_healthy images)
Total: 496 images across 6 distinct crop-disease classes.

Splits data 80% train / 20% val in standard YOLO-cls directory format.
Validates all image files before inclusion.
"""

import json
import random
import shutil
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "ai" / "data" / "dataset_disease"
SEED = 42
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Verified sources: (repo, relative_folder_path, target_class_name)
SOURCES = [
    ("pratikkayal/PlantDoc-Dataset", "train/Tomato Early blight leaf", "tomato_early_blight"),
    ("pratikkayal/PlantDoc-Dataset", "train/Tomato leaf late blight", "tomato_late_blight"),
    ("pratikkayal/PlantDoc-Dataset", "train/Tomato leaf", "tomato_healthy"),
    ("pratikkayal/PlantDoc-Dataset", "train/Potato leaf early blight", "potato_early_blight"),
    ("pratikkayal/PlantDoc-Dataset", "train/Potato leaf late blight", "potato_late_blight"),
    ("spMohanty/PlantVillage-Dataset", "raw/color/Potato___healthy", "potato_healthy"),
]


def fetch_image_list(repo: str, rel_path: str):
    url = f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(rel_path)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read().decode())
    return [i for i in items if i["name"].lower().endswith((".jpg", ".jpeg", ".png"))]


def download_single_image(task):
    url, dest = task
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        # Verify image integrity using PIL
        with Image.open(dest) as img:
            img.verify()
        return True
    except Exception as e:
        if dest.exists():
            dest.unlink()
        print(f"Skipping corrupt/failed image {url}: {e}")
        return False


def main():
    random.seed(SEED)
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)

    summary = {}
    download_tasks = []
    metadata = {}

    print("=== STARTING FAST MULTI-THREADED DATASET INGESTION ===")

    for repo, rel_path, cls_name in SOURCES:
        print(f"Fetching manifest: {cls_name} from {repo}/{rel_path}...")
        items = fetch_image_list(repo, rel_path)

        # Cap potato_healthy at 55 to keep dataset balanced with tomato_healthy (55)
        if cls_name == "potato_healthy" and len(items) > 55:
            items = items[:55]

        random.shuffle(items)
        n_train = int(len(items) * 0.80)
        splits = {"train": items[:n_train], "val": items[n_train:]}

        metadata[cls_name] = {"train": 0, "val": 0, "total": 0}

        for split_name, split_items in splits.items():
            for idx, item in enumerate(split_items):
                download_url = item["download_url"]
                ext = Path(item["name"]).suffix or ".jpg"
                filename = f"{cls_name}_{idx:03d}{ext}"
                dest_path = DATASET_DIR / split_name / cls_name / filename

                download_tasks.append((download_url, dest_path, cls_name, split_name))

    print(f"\nDownloading {len(download_tasks)} image files with 16 parallel threads...")

    completed = 0
    with ThreadPoolExecutor(max_workers=16) as executor:
        future_to_task = {
            executor.submit(download_single_image, (url, dest)): (cls_name, split_name)
            for url, dest, cls_name, split_name in download_tasks
        }
        for future in as_completed(future_to_task):
            cls_name, split_name = future_to_task[future]
            if future.result():
                metadata[cls_name][split_name] += 1
                metadata[cls_name]["total"] += 1
                completed += 1

    summary_file = DATASET_DIR / "dataset_summary.json"
    summary_file.write_text(json.dumps(metadata, indent=2))

    print("\n=== VERIFIED DATASET SUMMARY ===")
    for cls, stats in metadata.items():
        print(f"  - {cls}: {stats['total']} total ({stats['train']} train, {stats['val']} val)")
    print(f"TOTAL VERIFIED IMAGES DOWNLOADED: {completed}")
    print(f"DATASET LOCATION: {DATASET_DIR.resolve()}")


if __name__ == "__main__":
    main()
