from datetime import datetime, timedelta

import numpy as np
from supervision import Detections

from edge.visual_recognition_edge.person_behavior import PersonBehaviorEngine, PersonObservation
from edge.visual_recognition_edge.pipeline import EdgePipeline
from edge.visual_recognition_edge.privacy import PrivacyProcessor


class FakeDetector:
    def __init__(self, detections):
        self.detections = detections

    def detect(self, frame):
        return self.detections


def detections(tracker_id=1):
    return Detections(
        xyxy=np.array([[250.0, 250.0, 350.0, 350.0]]),
        confidence=np.array([0.9]),
        class_id=np.array([2]),
        tracker_id=np.array([tracker_id]),
    )


def pipeline():
    return EdgePipeline(
        camera_id="cam-test",
        area_id="area-test",
        model_path="unused",
        api_base_url="http://localhost",
        api_key="unused",
        area_polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        stay_threshold_seconds=5,
        high_risk_seconds=10,
        keyframe_interval_seconds=10,
        movement_threshold_pixels=15,
        lost_track_tolerance_seconds=2,
        detector=FakeDetector(detections()),
    )


def frame():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def test_pipeline_reports_after_real_seconds_and_tolerates_brief_loss():
    edge = pipeline()
    start = datetime(2026, 9, 24, 10, 0, 0)
    first = edge.process_frame(frame(), 0, start)
    assert first is not None
    assert first.track_id == "track-cam-test-1"

    assert edge.process_frame(frame(), 1, start + timedelta(seconds=2)) is None

    reported = edge.process_frame(frame(), 2, start + timedelta(seconds=5))
    assert reported is not None
    assert reported.keyframe_role == "static_start"
    assert reported.static_seconds == 5.0

    missing = edge.process_frame(frame(), 3, start + timedelta(seconds=6))
    assert missing is None
    assert edge.tracks

    detector = FakeDetector(detections())
    edge.detector = detector
    recovered = edge.process_frame(frame(), 4, start + timedelta(seconds=7))
    assert recovered is None
    assert edge.tracks[1].event_reported is True


def test_pipeline_clears_track_after_lost_tolerance():
    edge = pipeline()
    start = datetime(2026, 9, 24, 10, 0, 0)
    edge.process_frame(frame(), 0, start)
    edge.detector = FakeDetector(Detections.empty())
    edge.process_frame(frame(), 1, start + timedelta(seconds=1))
    edge.process_frame(frame(), 2, start + timedelta(seconds=3.5))
    assert not edge.tracks


def test_polygon_supports_pixel_and_normalized_coordinates():
    edge = pipeline()
    normalized = edge.normalize_polygon(frame())
    assert normalized[0] == [128.0, 72.0]

    edge.area_polygon = [[100, 100], [1180, 100], [1180, 620], [100, 620]]
    pixel = edge.normalize_polygon(frame())
    assert pixel[0] == [100.0, 100.0]


def test_person_behavior_engine_escalates_to_loitering():
    engine = PersonBehaviorEngine(loitering_seconds=120)
    observation = PersonObservation(
        person_track_id="track-person-1",
        vehicle_track_id="track-vehicle-1",
        vehicle_box=(200, 200, 400, 400),
        bbox=(240, 240, 320, 340),
        confidence=0.85,
        keypoints=[],
        center=(280, 290),
    )
    start = datetime(2026, 9, 24, 10, 0, 0)
    first = engine.observe(observation, start)
    assert first.behavior_label == "person_present"
    assert first.near_vehicle_seconds == 0

    second = engine.observe(observation, start + timedelta(seconds=130))
    assert second.behavior_label == "long_time_loitering"
    assert second.near_vehicle_seconds == 130
    assert second.sequence_frame_count == 2


class FakePersonPoseDetector:
    available = True

    def detect(self, frame, vehicles):
        assert vehicles
        vehicle_track_id, vehicle_box = vehicles[0]
        return [
            PersonObservation(
                person_track_id="track-cam-test-person-1",
                vehicle_track_id=vehicle_track_id,
                vehicle_box=vehicle_box,
                bbox=(260.0, 260.0, 340.0, 340.0),
                confidence=0.8,
                keypoints=[],
                center=(300.0, 300.0),
            )
        ]


def test_pipeline_attaches_person_behavior_to_event_frame():
    edge = EdgePipeline(
        camera_id="cam-test",
        area_id="area-test",
        model_path="unused",
        api_base_url="http://localhost",
        api_key="unused",
        area_polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        stay_threshold_seconds=1,
        high_risk_seconds=10,
        keyframe_interval_seconds=10,
        movement_threshold_pixels=15,
        lost_track_tolerance_seconds=2,
        detector=FakeDetector(detections()),
        person_detector=FakePersonPoseDetector(),
    )
    result = edge.process_frame(frame(), 0, datetime(2026, 9, 24, 10, 0, 0))
    assert result is not None
    assert result.behavior_results
    assert result.behavior_results[0].person_track_id == "track-cam-test-person-1"
    assert result.behavior_results[0].vehicle_track_id == "track-cam-test-1"
    assert result.behavior_results[0].behavior_label == "person_present"


def test_privacy_processor_blurs_face_and_plate_regions():
    processor = PrivacyProcessor(mosaic_size=4)
    frame = np.zeros((400, 720, 3), dtype=np.uint8)
    # 在人脸区填充带噪声的纹理，便于验证马赛克效果
    rng = np.random.default_rng(42)
    face_area = rng.integers(0, 255, size=(80, 60, 3), dtype=np.uint8)
    frame[60:140, 160:220] = face_area
    # 车牌条带同样填充噪声
    plate_area = rng.integers(0, 255, size=(20, 220, 3), dtype=np.uint8)
    frame[300:320, 90:310] = plate_area

    observation = PersonObservation(
        person_track_id="p1",
        vehicle_track_id="v1",
        vehicle_box=(100, 200, 300, 320),
        bbox=(160, 60, 220, 140),
        confidence=0.9,
        keypoints=[{"name": "nose", "xy": [190.0, 90.0], "score": 0.95}],
        center=(190.0, 90.0),
    )
    vehicle_box = (100, 200, 300, 320)
    original = frame.copy()
    blurred = processor.process(frame, [observation], [vehicle_box])

    # 输出帧不应与原始帧完全相同
    assert not np.array_equal(original, blurred)

    # 人脸区域被马赛克：原图人脸区与模糊后人脸区必须不同
    face_region_original = original[60:140, 160:220]
    face_region_blurred = blurred[60:140, 160:220]
    assert face_region_original.shape == face_region_blurred.shape
    assert not np.array_equal(face_region_original, face_region_blurred)

    # 车牌条带被马赛克
    plate_original = original[300:320, 90:310]
    plate_blurred = blurred[300:320, 90:310]
    assert plate_original.shape == plate_blurred.shape
    assert not np.array_equal(plate_original, plate_blurred)

    # 非敏感区域应保持不变
    untouched_original = original[0:50, 0:50]
    untouched_blurred = blurred[0:50, 0:50]
    assert np.array_equal(untouched_original, untouched_blurred)


def test_privacy_processor_no_op_when_no_observations():
    processor = PrivacyProcessor(mosaic_size=4)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    out = processor.process(frame, [], [])
    assert np.array_equal(frame, out)
