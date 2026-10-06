"""Classifies a patient's state from a camera frame using a YOLO model.

Plain Python, no ROS: keeps application logic out of ROS nodes.
"""

from enum import Enum
from typing import Any


class PatientState(Enum):
    """The three patient states the mission needs to distinguish."""

    IN_BED = 'in_bed'
    ON_FLOOR = 'on_floor'
    STANDING = 'standing'


def state_from_boxes(boxes: Any, names: dict[int, str]) -> PatientState | None:
    """Return the highest-confidence patient state among detected boxes.

    Returns None for an empty `boxes`: a frame with no confident detection
    is an expected outcome (patient briefly occluded), not an error. Kept
    free of the YOLO/ultralytics import so it's testable without that
    dependency installed.
    """
    if len(boxes) == 0:
        return None

    best_box = max(boxes, key=lambda box: box.conf)
    return PatientState(names[int(best_box.cls)])


class PatientDetector:
    """Runs YOLO inference on a frame and returns the top-confidence state."""

    def __init__(self, weights_path: str, min_confidence: float = 0.5) -> None:
        from ultralytics import YOLO  # heavy, ROS-node-only dependency

        self._model = YOLO(weights_path)
        self._min_confidence = min_confidence

    def detect(self, frame: Any) -> PatientState | None:
        """Return the highest-confidence patient state found in the frame."""
        results = self._model.predict(frame, conf=self._min_confidence, verbose=False)
        return state_from_boxes(results[0].boxes, self._model.names)
