import argparse
import os

import cv2
from datetime import datetime, timedelta

from edge.visual_recognition_edge.config import EdgeSettings
from edge.visual_recognition_edge.pipeline import EdgePipeline


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()
    settings = EdgeSettings(_env_file=os.getenv("EDGE_ENV_FILE", ".env"))
    pipeline = EdgePipeline(
        camera_id=settings.camera_id,
        area_id=settings.area_id,
        model_path=settings.model_path,
        api_base_url=settings.api_base_url,
        area_polygon=settings.area_polygon,
        api_key=settings.api_key,
        stay_threshold_seconds=settings.stay_threshold_seconds,
        high_risk_seconds=settings.high_risk_seconds,
        keyframe_interval_seconds=settings.keyframe_interval_seconds,
        movement_threshold_pixels=settings.movement_threshold_pixels,
        lost_track_tolerance_seconds=settings.lost_track_tolerance_seconds,
    )
    capture = cv2.VideoCapture(settings.video_source)
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    is_network_stream = str(settings.video_source).lower().startswith(("rtsp://", "http://", "https://"))
    use_video_time = settings.video_timestamp_mode == "video" or (
        settings.video_timestamp_mode == "auto" and not is_network_stream
    )
    video_start_time = datetime.now()
    frame_index = 0
    while capture.isOpened():
        ok, frame = capture.read()
        if not ok:
            break
        captured_at = (
            video_start_time + timedelta(seconds=frame_index / fps)
            if use_video_time
            else datetime.now()
        )
        result = pipeline.process_frame(frame, frame_index, captured_at)
        if result:
            pipeline.upload_keyframe(frame, result)
        frame_index += 1
        if settings.frame_stride > 1:
            for _ in range(settings.frame_stride - 1):
                if not capture.grab():
                    break
                frame_index += 1
        if args.max_frames and frame_index >= args.max_frames:
            break
    capture.release()


if __name__ == "__main__":
    run()
