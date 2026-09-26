"""边缘端隐私处理：上传关键帧前对人脸/车牌区域做马赛克。"""

from __future__ import annotations

import numpy as np

from edge.visual_recognition_edge.person_behavior import PersonObservation


class PrivacyProcessor:
    """对关键帧做人脸与车牌区域马赛克，避免直接上传原始人脸/车牌像素。"""

    def __init__(
        self,
        mosaic_size: int = 12,
        face_padding_ratio: float = 0.6,
        plate_strip_ratio: float = 0.22,
        plate_padding: int = 6,
    ) -> None:
        if mosaic_size < 2:
            raise ValueError("mosaic_size must be >= 2")
        self.mosaic_size = mosaic_size
        self.face_padding_ratio = face_padding_ratio
        self.plate_strip_ratio = plate_strip_ratio
        self.plate_padding = plate_padding

    def process(
        self,
        frame: np.ndarray,
        person_observations: list[PersonObservation],
        vehicle_boxes: list[tuple[float, float, float, float]],
    ) -> np.ndarray:
        """返回脱敏后的新帧；原帧不被修改。"""
        result = frame.copy()
        result = self._blur_faces(result, person_observations)
        result = self._blur_plates(result, vehicle_boxes)
        return result

    # ---- 内部工具 ----

    def _blur_faces(self, frame: np.ndarray, observations: list[PersonObservation]) -> np.ndarray:
        for observation in observations:
            nose = self._find_nose(observation)
            if nose is None:
                continue
            nx, ny = nose
            width = max(observation.bbox[2] - observation.bbox[0], 1.0)
            height = max(observation.bbox[3] - observation.bbox[1], 1.0)
            side = max(width, height) * self.face_padding_ratio
            x1 = int(max(0, nx - side / 2))
            y1 = int(max(0, ny - side / 2))
            x2 = int(min(frame.shape[1], nx + side / 2))
            y2 = int(min(frame.shape[0], ny + side / 2))
            if x2 - x1 < 2 or y2 - y1 < 2:
                continue
            self._mosaic(frame, x1, y1, x2, y2)
        return frame

    def _blur_plates(self, frame: np.ndarray, vehicle_boxes: list[tuple[float, float, float, float]]) -> np.ndarray:
        height, width = frame.shape[:2]
        for box in vehicle_boxes:
            x1, y1, x2, y2 = box
            box_height = max(y2 - y1, 1.0)
            strip_top = int(y2 - box_height * self.plate_strip_ratio)
            strip_top = max(0, min(height - 2, strip_top))
            strip_bottom = int(min(height, y2))
            strip_left = int(max(0, x1 - self.plate_padding))
            strip_right = int(min(width, x2 + self.plate_padding))
            if strip_right - strip_left < 2 or strip_bottom - strip_top < 2:
                continue
            self._mosaic(frame, strip_left, strip_top, strip_right, strip_bottom)
        return frame

    @staticmethod
    def _find_nose(observation: PersonObservation) -> tuple[float, float] | None:
        for keypoint in observation.keypoints or []:
            name = str(keypoint.get("name", "")).lower()
            if name in {"nose"} and float(keypoint.get("score", 0.0)) >= 0.3:
                xy = keypoint.get("xy") or keypoint.get("x")
                if isinstance(xy, (list, tuple)) and len(xy) == 2:
                    return float(xy[0]), float(xy[1])
        # 没有鼻尖时退化为包围框中心
        bbox = observation.bbox
        return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0

    def _mosaic(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
        region = frame[y1:y2, x1:x2]
        if region.size == 0:
            return
        h, w = region.shape[:2]
        # 下采样到 mosaic_size x mosaic_size，再上采样回原尺寸
        small_h = max(1, min(h, self.mosaic_size))
        small_w = max(1, min(w, self.mosaic_size))
        if small_h == h and small_w == w:
            return
        # cv2 不在依赖里，用 numpy 简易实现：按块取均值
        ys = np.linspace(0, h, small_h + 1).astype(int)
        xs = np.linspace(0, w, small_w + 1).astype(int)
        block = np.zeros((small_h, small_w, region.shape[2]), dtype=region.dtype)
        for i in range(small_h):
            for j in range(small_w):
                y0, y1_ = ys[i], ys[i + 1]
                x0, x1_ = xs[j], xs[j + 1]
                if y1_ <= y0 or x1_ <= x0:
                    continue
                block[i, j] = region[y0:y1_, x0:x1_].reshape(-1, region.shape[2]).mean(axis=0)
        # 上采样回原尺寸
        restored = np.zeros_like(region)
        for i in range(small_h):
            for j in range(small_w):
                y0, y1_ = ys[i], ys[i + 1]
                x0, x1_ = xs[j], xs[j + 1]
                if y1_ <= y0 or x1_ <= x0:
                    continue
                restored[y0:y1_, x0:x1_] = block[i, j]
        frame[y1:y2, x1:x2] = restored