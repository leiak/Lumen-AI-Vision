from __future__ import annotations

import os
from pathlib import Path


def configure_yolo_runtime() -> None:
    if not os.environ.get("YOLO_CONFIG_DIR"):
        project_root = Path(__file__).resolve().parents[2]
        os.environ["YOLO_CONFIG_DIR"] = str(project_root / ".ultralytics")
