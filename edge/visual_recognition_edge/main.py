import argparse
import os
import threading

import cv2
import httpx
from datetime import datetime, timedelta

from edge.visual_recognition_edge.config import EdgeSettings
from edge.visual_recognition_edge.pipeline import EdgePipeline


CONFIG_POLL_INTERVAL_SECONDS = 30


def _start_config_poller(pipeline: EdgePipeline) -> None:
    """后台线程：定时拉取 /edge/config 并热更新阈值。"""

    def loop() -> None:
        while True:
            try:
                response = httpx.get(
                    f"{pipeline.api_base_url}/api/v1/edge/config",
                    params={"camera_id": pipeline.camera_id, "area_id": pipeline.area_id},
                    headers={"X-API-Key": pipeline.api_key},
                    timeout=10,
                )
                response.raise_for_status()
                applied = pipeline.apply_remote_config(response.json())
                if applied:
                    print(f"[edge] hot-reload applied: {applied}")
            except Exception as exc:  # pragma: no cover - 网络抖动不致命
                print(f"[edge] config poll failed: {exc}")
            import time
            time.sleep(CONFIG_POLL_INTERVAL_SECONDS)

    thread = threading.Thread(target=loop, daemon=True, name="edge-config-poller")
    thread.start()


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
        pose_model_path=settings.pose_model_path,
        pose_sample_fps=settings.pose_sample_fps,
        person_max_tracks=settings.person_max_tracks,
        person_near_vehicle_margin_pixels=settings.person_near_vehicle_margin_pixels,
        person_loitering_seconds=settings.person_loitering_seconds,
        person_movement_threshold_pixels=settings.person_movement_threshold_pixels,
        person_lost_tolerance_seconds=settings.person_lost_tolerance_seconds,
    )
    _start_config_poller(pipeline)
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
