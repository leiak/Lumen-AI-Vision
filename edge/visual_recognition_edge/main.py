import argparse

import cv2

from edge.visual_recognition_edge.config import EdgeSettings
from edge.visual_recognition_edge.pipeline import EdgePipeline


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()
    settings = EdgeSettings()
    pipeline = EdgePipeline(
        camera_id=settings.camera_id,
        area_id=settings.area_id,
        model_path=settings.model_path,
        api_base_url=settings.api_base_url,
        area_polygon=settings.area_polygon,
        api_key=settings.api_key,
    )
    capture = cv2.VideoCapture(settings.video_source)
    frame_index = 0
    while capture.isOpened():
        ok, frame = capture.read()
        if not ok:
            break
        result = pipeline.process_frame(frame, frame_index)
        if result and frame_index % max(1, settings.keyframe_interval_seconds * 25) == 0:
            pipeline.upload_keyframe(frame, result)
        frame_index += 1
        if args.max_frames and frame_index >= args.max_frames:
            break
    capture.release()


if __name__ == "__main__":
    run()
