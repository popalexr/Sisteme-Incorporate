from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class CameraConfig:
    width: int = 1280
    height: int = 720
    prefer_picamera2: bool = True


class CameraStream:
    """Unified camera interface for Raspberry Pi (Picamera2) and USB/OpenCV cameras."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._backend = None
        self._picam2 = None
        self._opencv_cap = None
        self._picamera2_error = None

    def start(self, force_backend: str = "auto") -> None:
        use_picamera2 = force_backend == "picamera2" or (
            force_backend == "auto" and self.config.prefer_picamera2
        )
        if use_picamera2:
            try:
                from picamera2 import Picamera2

                self._picam2 = Picamera2()
                camera_config = self._picam2.create_video_configuration(
                    main={"size": (self.config.width, self.config.height), "format": "RGB888"}
                )
                self._picam2.configure(camera_config)
                self._picam2.start()
                self._backend = "picamera2"
                return
            except Exception as exc:
                self._picamera2_error = f"{type(exc).__name__}: {exc}"
                self._picam2 = None
                if force_backend == "picamera2":
                    raise RuntimeError(
                        "Could not start Picamera2 backend. "
                        f"Details: {self._picamera2_error}"
                    ) from exc

        if force_backend not in ("auto", "opencv"):
            raise ValueError(
                "Invalid backend selection. Use one of: auto, picamera2, opencv."
            )

        self._opencv_cap = cv2.VideoCapture(0)
        if not self._opencv_cap.isOpened():
            picamera_note = (
                f" Picamera2 error: {self._picamera2_error}"
                if self._picamera2_error
                else ""
            )
            raise RuntimeError(
                "No camera available. Verify camera connection and Picamera2/OpenCV setup."
                + picamera_note
            )

        self._opencv_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._opencv_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._backend = "opencv"

    def read(self) -> np.ndarray:
        if self._backend == "picamera2" and self._picam2 is not None:
            rgb_frame = self._picam2.capture_array()
            return cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

        if self._backend == "opencv" and self._opencv_cap is not None:
            ok, frame = self._opencv_cap.read()
            if not ok:
                raise RuntimeError(
                    "Failed to read frame from OpenCV camera backend. "
                    "On Raspberry Pi camera module, run with --backend picamera2."
                )
            return frame

        raise RuntimeError("CameraStream not started.")

    def stop(self) -> None:
        if self._picam2 is not None:
            try:
                self._picam2.stop()
            except Exception:
                pass
            self._picam2 = None

        if self._opencv_cap is not None:
            self._opencv_cap.release()
            self._opencv_cap = None

        self._backend = None

    @property
    def backend(self) -> str | None:
        return self._backend

    @property
    def picamera2_error(self) -> str | None:
        return self._picamera2_error
