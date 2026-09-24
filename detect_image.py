from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect objects in one image with YOLOv8n.")
    parser.add_argument("image", nargs="?", default="两个人物.png", help="Input image path")
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO model path")
    parser.add_argument("--conf", type=float, default=0.10, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold")
    parser.add_argument("--imgsz", type=int, default=1280, help="Inference image size")
    parser.add_argument("--device", default="cpu", help="cpu, cuda, or mps")
    parser.add_argument("--persons-only", action="store_true", help="Only detect person class")
    parser.add_argument("--output-root", default="output/detections", help="Detection output directory")
    return parser.parse_args()


def resolve_path(value: str, root: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def find_annotated_image(output_dir: Path, image_path: Path, json_path: Path) -> Path:
    candidates = [
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.stem == image_path.stem and path != json_path
    ]
    return candidates[0] if candidates else output_dir


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent
    image_path = resolve_path(args.image, root)
    model_path = resolve_path(args.model, root)

    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")
    if not model_path.exists():
        raise SystemExit(f"Model not found: {model_path}")

    os.environ.setdefault("YOLO_CONFIG_DIR", str(root / ".ultralytics"))
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    result = model.predict(
        source=str(image_path),
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device,
        classes=[0] if args.persons_only else None,
        save=True,
        project=str(resolve_path(args.output_root, root)),
        name=image_path.stem,
        exist_ok=True,
        verbose=False,
    )[0]

    output_dir = Path(result.save_dir)
    json_path = output_dir / "detections.json"
    detections = []
    for box in result.boxes:
        class_id = int(box.cls.item())
        detections.append(
            {
                "class": result.names[class_id],
                "class_id": class_id,
                "confidence": round(float(box.conf.item()), 4),
                "box_xyxy": [round(float(value), 1) for value in box.xyxy[0].tolist()],
            }
        )

    payload = {
        "image": str(image_path),
        "model": str(model_path),
        "confidence_threshold": args.conf,
        "detections": detections,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Image: {image_path}")
    print(f"Detections: {len(detections)}")
    for index, detection in enumerate(detections, start=1):
        confidence = detection["confidence"]
        box = detection["box_xyxy"]
        print(f"{index}. {detection['class']}  confidence={confidence:.3f}  box={box}")
    print(f"Annotated image: {find_annotated_image(output_dir, image_path, json_path)}")
    print(f"Detections JSON: {json_path}")


if __name__ == "__main__":
    main()
