"""
YOLOv8 Fine-Tuning Script for Flour Bag Detection.

Prerequisites:
    pip install ultralytics albumentations opencv-python-headless

Dataset structure expected (YOLO format):
    data/
    ├── images/
    │   ├── train/          # .jpg / .png
    │   └── val/
    ├── labels/
    │   ├── train/          # .txt (YOLO: class x_center y_center width height)
    │   └── val/
    └── data.yaml

data.yaml example:
    path: ./data
    train: images/train
    val: images/val
    nc: 3
    names: ['empty_bag', 'bag_25kg', 'bag_50kg']

Usage:
    python -m src.training.finetune_yolo --data data/data.yaml --epochs 100 --imgsz 640
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Optional

from ultralytics import YOLO
from loguru import logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune YOLOv8 for bag detection")
    parser.add_argument("--data", type=str, required=True, help="Path to data.yaml")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base model (n/s/m/l/x)")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--workers", type=int, default=4, help="Dataloader workers")
    parser.add_argument("--device", type=str, default="cpu", help="Device: cpu or 0,1,...")
    parser.add_argument("--project", type=str, default="runs/bag_training", help="Output dir")
    parser.add_argument("--name", type=str, default="bag_yolo", help="Run name")
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience")
    parser.add_argument("--lr0", type=float, default=0.01, help="Initial learning rate")
    parser.add_argument("--lrf", type=float, default=0.01, help="Final learning rate factor")
    parser.add_argument("--mosaic", type=float, default=1.0, help="Mosaic augmentation (0-1)")
    parser.add_argument("--mixup", type=float, default=0.1, help="Mixup augmentation (0-1)")
    parser.add_argument("--resume", action="store_true", help="Resume last run")
    parser.add_argument("--export", action="store_true", help="Export to ONNX after training")
    parser.add_argument("--export-int8", action="store_true", help="Export INT8 ONNX for Edge")
    parser.add_argument("--copy-best", type=str, default="models/best_bag.pt",
                        help="Copy best weights to this path")
    return parser.parse_args()


def setup_environment() -> None:
    """Ensure deterministic behaviour where possible."""
    os.environ["PYTHONHASHSEED"] = "42"
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"


def train(args: argparse.Namespace) -> None:
    logger.info(f"Loading base model: {args.model}")
    model = YOLO(args.model)

    logger.info("Starting training...")
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=args.device,
        project=args.project,
        name=args.name,
        patience=args.patience,
        lr0=args.lr0,
        lrf=args.lrf,
        mosaic=args.mosaic,
        mixup=args.mixup,
        resume=args.resume,
        seed=42,
        verbose=True,
        # Bag-specific augmentations
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5.0,
        translate=0.1,
        scale=0.5,
        shear=2.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.5,
        bgr=0.0,
        copy_paste=0.0,
        auto_augment="randaugment",
        erasing=0.4,
        crop_fraction=1.0,
    )

    best_path = Path(args.project) / args.name / "weights" / "best.pt"
    logger.info(f"Training complete. Best weights: {best_path}")

    # Copy to project models/
    if best_path.exists():
        dst = Path(args.copy_best)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_path, dst)
        logger.info(f"Copied best weights -> {dst}")

    # Validation on best
    logger.info("Running validation on best weights...")
    metrics = model.val(data=args.data, split="val", device=args.device)
    logger.info(f"mAP50-95: {metrics.box.map:.4f} | mAP50: {metrics.box.map50:.4f}")

    # Export
    if args.export:
        logger.info("Exporting to ONNX...")
        export_path = model.export(format="onnx", imgsz=args.imgsz, half=False)
        logger.info(f"ONNX saved: {export_path}")

    if args.export_int8:
        logger.info("Exporting INT8 ONNX (Edge-optimized)...")
        # INT8 requires calibration data; simplified here
        export_path = model.export(
            format="onnx",
            imgsz=args.imgsz,
            half=False,
            int8=True,
            data=args.data,
        )
        logger.info(f"INT8 ONNX saved: {export_path}")


def infer_example(weights: str = "models/best_bag.pt", source: str = "0") -> None:
    """Quick inference test on webcam or video."""
    model = YOLO(weights)
    results = model.predict(source=source, show=True, conf=0.5)
    logger.info(f"Inference on {source} complete.")


if __name__ == "__main__":
    setup_environment()
    args = parse_args()
    train(args)
