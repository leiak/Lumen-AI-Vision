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
    track_id: str
    static_seconds: float


@dataclass
class TrackState:
    track_id: str
    enter_time: datetime
    static_start_time: datetime | None = None
    last_seen_time: datetime | None = None
    event_reported: bool = False
    last_keyframe_time: datetime | None = None
    last_center: tuple[float, float] | None = None


class VehicleDetector:
    def __init__(self, model_path: str) -> None:
        self.model = YOLO(model_path)
        self.tracker = ByteTrack()

    def detect(self, frame: np.ndarray) -> Detections:
        result = self.model(frame, verbose=False)[0]
        detections = Detections.from_ultralytics(result)
        vehicle_mask = np.isin(detections.class_id, np.array([2, 3, 5, 7]))
        return self.tracker.update_with_detections(detections[vehicle_mask])


class EdgePipeline:
    def __init__(
        self,
        camera_id: str,
        area_id: str,
        model_path: str,
        api_base_url: str,
        area_polygon: list[list[float]],
        api_key: str,
        stay_threshold_seconds: float = 300,
        high_risk_seconds: float = 600,
        keyframe_interval_seconds: float = 10,
        movement_threshold_pixels: float = 15.0,
        lost_track_tolerance_seconds: float = 2.0,
        detector: VehicleDetector | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.area_id = area_id
        self.detector = detector or VehicleDetector(model_path)
        self.api_base_url = api_base_url.rstrip("/")
        self.area_polygon = area_polygon
        self.api_key = api_key
        self.stay_threshold_seconds = stay_threshold_seconds
        self.high_risk_seconds = high_risk_seconds
        self.keyframe_interval_seconds = keyframe_interval_seconds
        self.movement_threshold_pixels = movement_threshold_pixels
        self.lost_track_tolerance_seconds = lost_track_tolerance_seconds
        self.tracks: dict[int, TrackState] = {}

    @staticmethod
    def center_in_polygon(center: tuple[float, float], polygon: list[list[float]]) -> bool:
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

    def normalize_polygon(self, frame: np.ndarray) -> list[list[float]]:
        height, width = frame.shape[:2]
        max_value = max(abs(float(value)) for row in self.area_polygon for value in row)
        if 0 < max_value <= 1:
            return [[float(value) * (width if column == 0 else height) for column, value in enumerate(row)] for row in self.area_polygon]
        return [[float(value) for value in row] for row in self.area_polygon]

    def process_frame(self, frame: np.ndarray, frame_index: int, captured_at: datetime | None = None) -> FrameResult | None:
        now = captured_at or datetime.utcnow()
        detections = self.detector.detect(frame)
        polygon = self.normalize_polygon(frame)
        if len(detections) == 0 or detections.tracker_id is None:
            for tracker_id in list(self.tracks):
                state = self.tracks[tracker_id]
                last_seen = state.last_seen_time or state.enter_time
                if (now - last_seen).total_seconds() > self.lost_track_tolerance_seconds:
                    del self.tracks[tracker_id]
            return None

        centers = [(float((box[0] + box[2]) / 2), float((box[1] + box[3]) / 2)) for box in detections.xyxy]
        candidates: list[tuple[int, float]] = []
        for tracker_id, center in zip(detections.tracker_id, centers, strict=False):
            if self.center_in_polygon(center, polygon):
                state = self.tracks.get(int(tracker_id))
                if state is None:
                    state = TrackState(track_id=f"track-{self.camera_id}-{int(tracker_id)}", enter_time=now)
                    state.static_start_time = now
                    self.tracks[int(tracker_id)] = state
                state.last_seen_time = now
                if (
                    state.last_center is not None
                    and ((center[0] - state.last_center[0]) ** 2 + (center[1] - state.last_center[1]) ** 2) ** 0.5
                    > self.movement_threshold_pixels
                ):
                    state.static_start_time = now
                    state.event_reported = False
                    state.last_keyframe_time = None
                state.last_center = center
                static_seconds = max(0.0, (now - (state.static_start_time or state.enter_time)).total_seconds())
                candidates.append((int(tracker_id), static_seconds))

        active_ids = {tracker_id for tracker_id, _ in candidates}
        detected_ids = {int(tracker_id) for tracker_id in detections.tracker_id}
        for tracker_id, state in self.tracks.items():
            if tracker_id in detected_ids:
                state.last_seen_time = now
        for tracker_id in list(self.tracks):
            if tracker_id not in active_ids and (
                tracker_id not in detected_ids
                or (now - (self.tracks[tracker_id].last_seen_time or self.tracks[tracker_id].enter_time)).total_seconds()
                > self.lost_track_tolerance_seconds
            ):
                del self.tracks[tracker_id]

        if not candidates:
            return None

        tracker_id, static_seconds = max(candidates, key=lambda item: item[1])
        state = self.tracks[tracker_id]
        should_report = not state.event_reported and static_seconds >= self.stay_threshold_seconds
        should_capture = should_report or (
            state.last_keyframe_time is None
            or (now - state.last_keyframe_time).total_seconds() >= self.keyframe_interval_seconds
        )
        if not should_capture:
            return None

        state.last_keyframe_time = now
        if should_report:
            state.event_reported = True
            role = "static_start"
        elif static_seconds >= self.high_risk_seconds:
            role = "high_risk"
        else:
            role = "state_change"
        return FrameResult(
            frame_id=f"{self.camera_id}-{frame_index:08d}",
            timestamp=now,
            detections=detections,
            keyframe_role=role,
            track_id=state.track_id,
            static_seconds=round(static_seconds, 2),
        )

    def upload_keyframe(self, frame: np.ndarray, result: FrameResult) -> dict[str, Any]:
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("failed to encode frame")
        start_time = datetime.fromtimestamp(result.timestamp.timestamp() - result.static_seconds)
        payload = {
            "camera_id": self.camera_id,
            "area_id": self.area_id,
            "track": {
                "id": result.track_id,
                "camera_id": self.camera_id,
                "area_id": self.area_id,
                "vehicle_type": "unknown",
                "start_time": start_time.isoformat(),
                "status": "static",
                "static_seconds": int(result.static_seconds),
            },
            "event_type_hint": "abnormal_stay",
            "start_time": start_time.isoformat(),
            "duration_seconds": int(result.static_seconds),
            "keyframes": [],
            "dedup_key": f"{result.track_id}:abnormal_stay",
        }
        response = httpx.post(
            f"{self.api_base_url}/api/v1/edge/events",
            json=payload,
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        upload_result = response.json()
        event_id = upload_result.get("event_id")
        if event_id:
            upload = httpx.post(
                f"{self.api_base_url}/api/v1/edge/keyframes/upload",
                data={
                    "track_id": result.track_id,
                    "event_id": event_id,
                    "frame_id": result.frame_id,
                    "frame_role": result.keyframe_role,
                    "timestamp": result.timestamp.isoformat(),
                    "static_seconds": str(int(result.static_seconds)),
                },
                files={"file": ("frame.jpg", encoded.tobytes(), "image/jpeg")},
                headers={"X-API-Key": self.api_key},
                timeout=30,
            )
            upload.raise_for_status()
            upload_result["uploaded_keyframe"] = upload.json()
        return upload_result
