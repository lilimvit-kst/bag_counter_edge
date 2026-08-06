"""
Dataset preparation helpers for bag annotation.
Converts COCO / LabelMe / CVAT formats to YOLO.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Tuple

import cv2
from loguru import logger


CLASS_MAP = {
    "empty_bag": 0,
    "bag_25kg": 1,
    "bag_50kg": 2,
}


def convert_labelme_to_yolo(
    json_dir: Path,
    output_dir: Path,
    class_map: dict[str, int] | None = None,
) -> None:
    """
    Convert LabelMe JSON annotations to YOLO .txt format.
    """
    cmap = class_map or CLASS_MAP
    output_dir.mkdir(parents=True, exist_ok=True)

    for json_file in sorted(json_dir.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        img_w = data["imageWidth"]
        img_h = data["imageHeight"]
        lines: List[str] = []

        for shape in data.get("shapes", []):
            label = shape["label"]
            if label not in cmap:
                logger.warning(f"Unknown label '{label}' in {json_file.name}, skipping.")
                continue
            cls_id = cmap[label]
            pts = shape["points"]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            x_center = ((x_min + x_max) / 2.0) / img_w
            y_center = ((y_min + y_max) / 2.0) / img_h
            w = (x_max - x_min) / img_w
            h = (y_max - y_min) / img_h

            lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}")

        out_file = output_dir / (json_file.stem + ".txt")
        out_file.write_text("\n".join(lines), encoding="utf-8")

    logger.info(f"Converted {len(list(json_dir.glob('*.json')))} annotations -> {output_dir}")


def split_dataset(
    image_dir: Path,
    label_dir: Path,
    output_root: Path,
    train_ratio: float = 0.8,
    seed: int = 42,
) -> Tuple[Path, Path]:
    """
    Split images+labels into train/val folders.
    Returns (train_dir, val_dir).
    """
    import random
    random.seed(seed)

    images = sorted(image_dir.glob("*"))
    images = [i for i in images if i.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")]
    random.shuffle(images)
    split_idx = int(len(images) * train_ratio)
    train_imgs = images[:split_idx]
    val_imgs = images[split_idx:]

    for subset, imgs in [("train", train_imgs), ("val", val_imgs)]:
        img_out = output_root / "images" / subset
        lbl_out = output_root / "labels" / subset
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for img in imgs:
            shutil.copy2(img, img_out / img.name)
            lbl = label_dir / (img.stem + ".txt")
            if lbl.exists():
                shutil.copy2(lbl, lbl_out / lbl.name)

    logger.info(f"Split complete: {len(train_imgs)} train, {len(val_imgs)} val")
    return output_root / "images" / "train", output_root / "images" / "val"


def generate_data_yaml(
    output_path: Path,
    dataset_root: Path,
    class_names: List[str],
) -> None:
    """Generate data.yaml for Ultralytics."""
    content = {
        "path": str(dataset_root.resolve()),
        "train": "images/train",
        "val": "images/val",
        "nc": len(class_names),
        "names": class_names,
    }
    output_path.write_text(json.dumps(content, indent=2).replace('"', '').replace(',', ''), encoding="utf-8")
    # Actually write proper YAML
    yaml_text = f"""path: {dataset_root.resolve()}
train: images/train
val: images/val
nc: {len(class_names)}
names: {class_names}
"""
    output_path.write_text(yaml_text, encoding="utf-8")
    logger.info(f"data.yaml written to {output_path}")
