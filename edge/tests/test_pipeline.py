from datetime import datetime, timedelta

import numpy as np
from supervision import Detections

from edge.visual_recognition_edge.pipeline import EdgePipeline


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
