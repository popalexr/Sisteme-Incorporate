from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Detection:
    class_id: int
    label: str
    confidence: float
    box: tuple[int, int, int, int]


class YOLOv4TinyDetector:
    def __init__(
        self,
        model_dir: str | Path,
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.4,
    ) -> None:
        model_path = Path(model_dir)
        cfg_path = model_path / "yolov4-tiny.cfg"
        weights_path = model_path / "yolov4-tiny.weights"
        names_path = model_path / "coco.names"

        if not cfg_path.exists() or not weights_path.exists() or not names_path.exists():
            raise FileNotFoundError(
                "Missing model files. Run: python scripts/download_model.py"
            )

        with names_path.open("r", encoding="utf-8") as f:
            self.classes = [line.strip() for line in f if line.strip()]
        if not self.classes:
            raise RuntimeError("coco.names is empty or invalid.")

        net = cv2.dnn.readNetFromDarknet(str(cfg_path), str(weights_path))
        self.model = cv2.dnn.DetectionModel(net)
        self.model.setInputParams(
            size=(416, 416),
            scale=1 / 255.0,
            swapRB=True,
        )
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        class_ids, confidences, boxes = self.model.detect(
            frame,
            confThreshold=self.confidence_threshold,
            nmsThreshold=self.nms_threshold,
        )

        results: list[Detection] = []
        if len(class_ids) == 0:
            return results

        for class_id, confidence, box in zip(
            np.array(class_ids).flatten().tolist(),
            np.array(confidences).flatten().tolist(),
            np.array(boxes).tolist(),
        ):
            normalized_class_id = class_id
            if normalized_class_id >= len(self.classes) and 1 <= class_id <= len(self.classes):
                normalized_class_id = class_id - 1
            if normalized_class_id < 0 or normalized_class_id >= len(self.classes):
                continue

            x, y, w, h = [int(v) for v in box]
            x1, y1 = x, y
            x2, y2 = x + w, y + h

            x1 = max(0, min(x1, width - 1))
            y1 = max(0, min(y1, height - 1))
            x2 = max(0, min(x2, width - 1))
            y2 = max(0, min(y2, height - 1))

            if x2 <= x1 or y2 <= y1:
                continue

            results.append(
                Detection(
                    class_id=normalized_class_id,
                    label=self.classes[normalized_class_id],
                    confidence=confidence,
                    box=(x1, y1, x2, y2),
                )
            )

        return results
