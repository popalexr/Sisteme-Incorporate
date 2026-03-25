from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


CLASSES = [
    "background",
    "aeroplane",
    "bicycle",
    "bird",
    "boat",
    "bottle",
    "bus",
    "car",
    "cat",
    "chair",
    "cow",
    "diningtable",
    "dog",
    "horse",
    "motorbike",
    "person",
    "pottedplant",
    "sheep",
    "sofa",
    "train",
    "tvmonitor",
]


@dataclass
class Detection:
    class_id: int
    label: str
    confidence: float
    box: tuple[int, int, int, int]


class MobileNetSSDDetector:
    def __init__(self, model_dir: str | Path, confidence_threshold: float = 0.5) -> None:
        model_path = Path(model_dir)
        prototxt = model_path / "deploy.prototxt"
        caffemodel = model_path / "mobilenet_iter_73000.caffemodel"

        if not prototxt.exists() or not caffemodel.exists():
            raise FileNotFoundError(
                "Missing model files. Run: python scripts/download_model.py"
            )

        self.net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
        self.confidence_threshold = confidence_threshold

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            image=cv2.resize(frame, (300, 300)),
            scalefactor=0.007843,
            size=(300, 300),
            mean=127.5,
        )

        self.net.setInput(blob)
        detections = self.net.forward()

        results: list[Detection] = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence < self.confidence_threshold:
                continue

            class_id = int(detections[0, 0, i, 1])
            if class_id < 0 or class_id >= len(CLASSES):
                continue

            box = detections[0, 0, i, 3:7] * np.array([width, height, width, height])
            x1, y1, x2, y2 = box.astype(int)

            x1 = max(0, min(x1, width - 1))
            y1 = max(0, min(y1, height - 1))
            x2 = max(0, min(x2, width - 1))
            y2 = max(0, min(y2, height - 1))

            if x2 <= x1 or y2 <= y1:
                continue

            results.append(
                Detection(
                    class_id=class_id,
                    label=CLASSES[class_id],
                    confidence=confidence,
                    box=(x1, y1, x2, y2),
                )
            )

        return results
