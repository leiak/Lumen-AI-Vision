from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from supervision import ByteTrack, Detections

from edge.visual_recognition_edge.runtime import configure_yolo_runtime

configure_yolo_runtime()

from ultralytics import YOLO


COCO_KEYPOINTS = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


def box_center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def box_iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def expand_box(box: tuple[float, float, float, float], margin: float) -> tuple[float, float, float, float]:
    return (
        max(0.0, box[0] - margin),
        max(0.0, box[1] - margin),
        box[2] + margin,
        box[3] + margin,
    )


@dataclass(frozen=True)
class PersonObservation:
    person_track_id: str
    vehicle_track_id: str | None
    vehicle_box: tuple[float, float, float, float] | None
    bbox: tuple[float, float, float, float]
    confidence: float
    keypoints: list[dict[str, Any]]
    center: tuple[float, float]

    @property
    def inside_vehicle(self) -> bool:
        if self.vehicle_box is None:
            return False
        return bool(self.vehicle_box[0] <= self.center[0] <= self.vehicle_box[2] and self.vehicle_box[1] <= self.center[1] <= self.vehicle_box[3])

    @property
    def keypoint_quality(self) -> float:
        if not self.keypoints:
            return 0.0
        visible = sum(float(item["score"]) >= 0.35 for item in self.keypoints)
        return min(1.0, visible / 8)


@dataclass(frozen=True)
class BehaviorResult:
    person_track_id: str
    vehicle_track_id: str | None
    behavior_label: str
    behavior_confidence: float
    near_vehicle_seconds: float
    sequence_frame_count: int
    sequence_start_time: datetime
    sequence_end_time: datetime
    model_type: str = "rule"
    model_version: str = "person-behavior-rule-v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_track_id": self.person_track_id,
            "vehicle_track_id": self.vehicle_track_id,
            "behavior_label": self.behavior_label,
            "behavior_confidence": self.behavior_confidence,
            "near_vehicle_seconds": round(self.near_vehicle_seconds, 2),
            "sequence_frame_count": self.sequence_frame_count,
            "sequence_start_time": self.sequence_start_time.isoformat(),
            "sequence_end_time": self.sequence_end_time.isoformat(),
            "model_type": self.model_type,
            "model_version": self.model_version,
        }


@dataclass
class PersonBehaviorState:
    vehicle_track_id: str | None
    first_seen_time: datetime
    last_seen_time: datetime
    last_center: tuple[float, float] | None = None
    sequence: list[dict[str, Any]] = field(default_factory=list)
    sequence_start_time: datetime | None = None
    labels: deque[str] = field(default_factory=lambda: deque(maxlen=5))


class PersonPoseDetector:
    def __init__(
        self,
        model_path: str,
        camera_id: str = "",
        confidence: float = 0.25,
        max_tracks: int = 5,
        near_vehicle_margin_pixels: float = 120.0,
    ) -> None:
        self.confidence = confidence
        self.max_tracks = max_tracks
        self.near_vehicle_margin_pixels = near_vehicle_margin_pixels
        self.model: YOLO | None = None
        self.tracker = ByteTrack()
        if model_path and Path(model_path).exists():
            self.model = YOLO(model_path)

    @property
    def available(self) -> bool:
        return self.model is not None

    def detect(
        self,
        frame: np.ndarray,
        vehicles: list[tuple[str, tuple[float, float, float, float]]],
    ) -> list[PersonObservation]:
        if self.model is None or not vehicles:
            return []

        result = self.model(frame, verbose=False)[0]
        all_detections = Detections.from_ultralytics(result)
        if len(all_detections) == 0:
            return []
        person_mask = all_detections.class_id == 0
        person_detections = all_detections[person_mask]
        if len(person_detections) == 0:
            return []

        tracked = self.tracker.update_with_detections(person_detections)
        if len(tracked) == 0 or tracked.tracker_id is None:
            return []

        source_boxes = person_detections.xyxy
        source_keypoints = getattr(person_detections.data, "keypoints", None)
        if source_keypoints is None and result.keypoints is not None:
            keypoint_xy = result.keypoints.xy.detach().cpu().numpy()
            keypoint_score = (
                result.keypoints.conf.detach().cpu().numpy()
                if result.keypoints.conf is not None
                else np.ones(keypoint_xy.shape[:2], dtype=np.float32)
            )
            source_keypoints = np.concatenate([keypoint_xy, keypoint_score[..., None]], axis=-1)

        observations: list[PersonObservation] = []
        for index, tracked_box_value in enumerate(tracked.xyxy):
            tracked_box = tuple(float(value) for value in tracked_box_value)
            source_index = self._nearest_source_index(tracked_box, source_boxes)
            keypoints = self._keypoint_payload(source_keypoints, source_index)
            tracker_id = int(tracked.tracker_id[index])
            vehicle_track_id, vehicle_box = self._nearest_vehicle(tracked_box, vehicles)
            if vehicle_track_id is None or vehicle_box is None:
                continue
            observations.append(
                PersonObservation(
                    person_track_id=f"track-{self.camera_id}-{tracker_id}" if self.camera_id else f"track-{tracker_id}",
                    vehicle_track_id=vehicle_track_id,
                    vehicle_box=vehicle_box,
                    bbox=tracked_box,
                    confidence=float(tracked.confidence[index]),
                    keypoints=keypoints,
                    center=box_center(tracked_box),
                )
            )

        return sorted(observations, key=lambda item: item.confidence, reverse=True)[: self.max_tracks]

    @staticmethod
    def _nearest_source_index(
        tracked_box: tuple[float, float, float, float],
        source_boxes: np.ndarray,
    ) -> int | None:
        if len(source_boxes) == 0:
            return None
        ious = [box_iou(tracked_box, tuple(float(value) for value in box)) for box in source_boxes]
        return int(max(range(len(ious)), key=lambda index: ious[index]))

    @staticmethod
    def _keypoint_payload(source_keypoints: np.ndarray | None, source_index: int | None) -> list[dict[str, Any]]:
        if source_keypoints is None or source_index is None or source_index >= len(source_keypoints):
            return []
        row = source_keypoints[source_index]
        payload: list[dict[str, Any]] = []
        for index, value in enumerate(row[: len(COCO_KEYPOINTS)]):
            x, y, score = (float(value[0]), float(value[1]), float(value[2])) if len(value) >= 3 else (float(value[0]), float(value[1]), 0.0)
            payload.append(
                {
                    "index": index,
                    "name": COCO_KEYPOINTS[index],
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "score": round(score, 4),
                }
            )
        return payload

    def _nearest_vehicle(
        self,
        person_box: tuple[float, float, float, float],
        vehicles: list[tuple[str, tuple[float, float, float, float]]],
    ) -> tuple[str | None, tuple[float, float, float, float] | None]:
        center = box_center(person_box)
        best: tuple[str | None, tuple[float, float, float, float] | None, float] = (None, None, -1.0)
        for vehicle_track_id, vehicle_box in vehicles:
            iou = box_iou(person_box, vehicle_box)
            expanded = expand_box(vehicle_box, self.near_vehicle_margin_pixels)
            inside = expanded[0] <= center[0] <= expanded[2] and expanded[1] <= center[1] <= expanded[3]
            if not inside:
                continue
            vehicle_center = box_center(vehicle_box)
            distance = ((center[0] - vehicle_center[0]) ** 2 + (center[1] - vehicle_center[1]) ** 2) ** 0.5
            score = iou * 100 - distance
            if score > best[2]:
                best = (vehicle_track_id, vehicle_box, score)
        return best[0], best[1]


class PersonBehaviorEngine:
    def __init__(
        self,
        loitering_seconds: float = 120.0,
        movement_threshold_pixels: float = 12.0,
        max_sequence_frames: int = 32,
    ) -> None:
        self.loitering_seconds = loitering_seconds
        self.movement_threshold_pixels = movement_threshold_pixels
        self.max_sequence_frames = max_sequence_frames
        self.states: dict[str, PersonBehaviorState] = {}
        self.latest_results: dict[str, BehaviorResult] = {}
        # 最近一次姿态观测（用于上传关键帧时反查人脸框）
        self.latest_observations: dict[str, PersonObservation] = {}

    def observe(
        self,
        observation: PersonObservation,
        now: datetime,
        nearby_person_count: int = 1,
    ) -> BehaviorResult:
        state = self.states.get(observation.person_track_id)
        if state is None or state.vehicle_track_id != observation.vehicle_track_id:
            state = PersonBehaviorState(
                vehicle_track_id=observation.vehicle_track_id,
                first_seen_time=now,
                last_seen_time=now,
            )
            self.states[observation.person_track_id] = state

        state.last_seen_time = now
        sample = {
            "timestamp": now.isoformat(),
            "bbox": list(observation.bbox),
            "confidence": observation.confidence,
            "keypoints": observation.keypoints,
        }
        state.sequence.append(sample)
        if len(state.sequence) > self.max_sequence_frames:
            state.sequence.pop(0)
        if state.sequence_start_time is None:
            state.sequence_start_time = now

        label = self._label(observation, state, now, nearby_person_count)
        state.labels.append(label)
        state.last_center = observation.center

        result = BehaviorResult(
            person_track_id=observation.person_track_id,
            vehicle_track_id=observation.vehicle_track_id,
            behavior_label=label,
            behavior_confidence=self._confidence(label, observation),
            near_vehicle_seconds=max(0.0, (now - state.first_seen_time).total_seconds()),
            sequence_frame_count=len(state.sequence),
            sequence_start_time=state.sequence_start_time or now,
            sequence_end_time=now,
        )
        self.latest_results[observation.person_track_id] = result
        self.latest_observations[observation.person_track_id] = observation
        return result

    def observations_for_frame(self, vehicle_track_id: str | None = None) -> list[PersonObservation]:
        """返回最近一次观测到的人员列表，可选按 vehicle_track_id 过滤。"""
        if vehicle_track_id is None:
            return list(self.latest_observations.values())
        return [
            observation
            for observation in self.latest_observations.values()
            if observation.vehicle_track_id == vehicle_track_id
        ]

    def results_for_vehicle(self, vehicle_track_id: str) -> list[BehaviorResult]:
        return [
            result
            for person_track_id, result in self.latest_results.items()
            if result.vehicle_track_id == vehicle_track_id and person_track_id in self.states
        ]

    def prune(self, now: datetime, tolerance_seconds: float) -> None:
        for person_track_id in list(self.states):
            state = self.states[person_track_id]
            if (now - state.last_seen_time).total_seconds() > tolerance_seconds:
                del self.states[person_track_id]
                self.latest_results.pop(person_track_id, None)

    def _label(
        self,
        observation: PersonObservation,
        state: PersonBehaviorState,
        now: datetime,
        nearby_person_count: int,
    ) -> str:
        immediate = self._immediate_label(observation)
        if immediate == "fall_down":
            return immediate
        if immediate == "person_entering_vehicle":
            return immediate

        if immediate == "person_present" and self._moving(state, observation):
            immediate = "person_moving"
        stable = self._stable_label(immediate, state)
        near_seconds = (now - state.first_seen_time).total_seconds()
        if near_seconds >= self.loitering_seconds:
            return "long_time_loitering"
        if nearby_person_count >= 2 and stable in {"person_present", "person_static", "person_moving"}:
            return "multiple_persons"
        if stable == "bending_or_crouching" and sum(value == "bending_or_crouching" for value in state.labels) >= 2:
            return "loading_unloading"
        return stable

    def _immediate_label(self, observation: PersonObservation) -> str:
        if observation.inside_vehicle and observation.keypoint_quality >= 0.6:
            return "person_entering_vehicle"
        if self._is_falling(observation):
            return "fall_down"
        if self._is_bending_or_crouching(observation):
            return "bending_or_crouching"
        return "person_present"

    def _stable_label(self, immediate: str, state: PersonBehaviorState) -> str:
        if immediate != "person_present":
            return immediate
        recent = list(state.labels)[-3:]
        if not recent:
            return "person_present"
        if "person_moving" in recent:
            return "person_moving"
        if len(recent) >= 2 and all(value == "person_static" for value in recent):
            return "person_static"
        return "person_present"

    @staticmethod
    def _visible_keypoints(observation: PersonObservation, indices: tuple[int, ...], threshold: float = 0.35) -> list[dict[str, Any]]:
        return [
            observation.keypoints[index]
            for index in indices
            if index < len(observation.keypoints) and float(observation.keypoints[index]["score"]) >= threshold
        ]

    @staticmethod
    def _is_falling(observation: PersonObservation) -> bool:
        shoulders = PersonBehaviorEngine._visible_keypoints(observation, (5, 6))
        hips = PersonBehaviorEngine._visible_keypoints(observation, (11, 12))
        knees = PersonBehaviorEngine._visible_keypoints(observation, (13, 14))
        if not shoulders or not hips or not knees:
            return False
        shoulder_y = sum(item["y"] for item in shoulders) / len(shoulders)
        hip_y = sum(item["y"] for item in hips) / len(hips)
        knee_y = sum(item["y"] for item in knees) / len(knees)
        return shoulder_y > hip_y and shoulder_y > knee_y

    @staticmethod
    def _is_bending_or_crouching(observation: PersonObservation) -> bool:
        shoulders = PersonBehaviorEngine._visible_keypoints(observation, (5, 6))
        hips = PersonBehaviorEngine._visible_keypoints(observation, (11, 12))
        if not shoulders or not hips:
            return False
        shoulder_y = sum(item["y"] for item in shoulders) / len(shoulders)
        hip_y = sum(item["y"] for item in hips) / len(hips)
        torso_length = abs(shoulder_y - hip_y)
        return torso_length < 18 or shoulder_y > hip_y

    @staticmethod
    def _confidence(label: str, observation: PersonObservation) -> float:
        base = {
            "fall_down": 0.90,
            "person_entering_vehicle": 0.85,
            "loading_unloading": 0.78,
            "long_time_loitering": 0.80,
            "multiple_persons": 0.72,
            "person_moving": 0.66,
            "person_static": 0.68,
            "person_present": 0.60,
            "unknown_behavior": 0.40,
        }.get(label, 0.55)
        return round(min(1.0, base * (0.65 + 0.35 * observation.keypoint_quality)), 4)

    def _moving(self, state: PersonBehaviorState, observation: PersonObservation) -> bool:
        if state.last_center is None:
            return False
        return ((observation.center[0] - state.last_center[0]) ** 2 + (observation.center[1] - state.last_center[1]) ** 2) ** 0.5 > self.movement_threshold_pixels
