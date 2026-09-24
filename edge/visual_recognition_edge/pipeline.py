from dataclasses import dataclass
from datetime import datetime
from typing import Any

import cv2
import httpx
import numpy as np
from supervision import ByteTrack, Detections
from ultralytics import YOLO


@dataclass
class FrameResult:
    frame_id: str
    timestamp: datetime
    detections: Detections
    keyframe_role: str


class VehicleDetector:
    def __init__(self, model_path: str) -> None:
        self.model = YOLO(model_path)
        self.tracker = ByteTrack()

    def detect(self, frame: np.ndarray) -> Detections:
        result = self.model(frame, verbose=False)[0]
        detections = Detections.from_ultralytics(result)
        return self.tracker.update_with_detections(detections)


class EdgePipeline:
    def __init__(self, camera_id: str, area_id: str, model_path: str, api_base_url: str, area_polygon: list[list[int]], api_key: str) -> None:
        self.camera_id = camera_id
        self.area_id = area_id
        self.detector = VehicleDetector(model_path)
        self.api_base_url = api_base_url.rstrip("/")
        self.last_static_time: datetime | None = None
        self.static_seconds = 0
        self.area_polygon = area_polygon
        self.api_key = api_key

    @staticmethod
    def center_in_polygon(center: tuple[float, float], polygon: list[list[int]]) -> bool:
        x, y = center
        inside = False
        prev = polygon[-1]
        for point in polygon:
            x1, y1 = point
            x2, y2 = prev
            if (y1 > y) != (y2 > y):
                intersect_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                if x < intersect_x:
                    inside = not inside
            prev = point
        return inside

    def process_frame(self, frame: np.ndarray, frame_index: int) -> FrameResult | None:
        now = datetime.utcnow()
        detections = self.detector.detect(frame)
        if len(detections) == 0 or detections.tracker_id is None:
            self.static_seconds = 0
            self.last_static_time = None
            return None
        centers = [(float((box[0] + box[2]) / 2), float((box[1] + box[3]) / 2)) for box in detections.xyxy]
        if not any(self.center_in_polygon(center, self.area_polygon) for center in centers):
            self.static_seconds = 0
            self.last_static_time = None
            return None
        self.static_seconds += 1
        role = "enter" if self.static_seconds == 1 else "state_change"
        if self.static_seconds % max(1, 10) == 0:
            role = "static_start"
        return FrameResult(
            frame_id=f"{self.camera_id}-{frame_index:08d}",
            timestamp=now,
            detections=detections,
            keyframe_role=role,
        )

    def upload_keyframe(self, frame: np.ndarray, result: FrameResult) -> dict[str, Any]:
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("failed to encode frame")
        payload = {
            "camera_id": self.camera_id,
            "area_id": self.area_id,
            "track": {
                "id": f"track-{self.camera_id}",
                "camera_id": self.camera_id,
                "area_id": self.area_id,
                "vehicle_type": "unknown",
                "start_time": result.timestamp.isoformat(),
                "status": "static",
                "static_seconds": self.static_seconds,
            },
            "event_type_hint": "abnormal_stay",
            "start_time": result.timestamp.isoformat(),
            "duration_seconds": self.static_seconds,
            "keyframes": [
                {
                    "id": result.frame_id,
                    "timestamp": result.timestamp.isoformat(),
                    "storage_url": f"local://{result.frame_id}.jpg",
                    "frame_role": result.keyframe_role,
                }
            ],
        }
        response = httpx.post(
            f"{self.api_base_url}/api/v1/edge/events",
            json=payload,
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        event_id = result.get("event_id")
        if event_id:
            _, encoded = cv2.imencode(".jpg", frame)
            upload = httpx.post(
                f"{self.api_base_url}/api/v1/edge/keyframes/upload",
                data={
                    "track_id": payload["track"]["id"],
                    "event_id": event_id,
                    "frame_role": result.keyframe_role,
                    "timestamp": result.timestamp.isoformat(),
                },
                files={"file": ("frame.jpg", encoded.tobytes(), "image/jpeg")},
                headers={"X-API-Key": self.api_key},
                timeout=30,
            )
            upload.raise_for_status()
            result["uploaded_keyframe"] = upload.json()
        return result
