from dataclasses import dataclass

from arams_mission.patient_detector import PatientState, state_from_boxes

_NAMES = {0: 'in_bed', 1: 'on_floor', 2: 'standing'}


@dataclass
class _FakeBox:
    cls: int
    conf: float


def test_no_boxes_returns_none():
    assert state_from_boxes([], _NAMES) is None


def test_single_box_returns_its_state():
    boxes = [_FakeBox(cls=1, conf=0.8)]
    assert state_from_boxes(boxes, _NAMES) == PatientState.ON_FLOOR


def test_returns_highest_confidence_box():
    boxes = [_FakeBox(cls=0, conf=0.6), _FakeBox(cls=2, conf=0.9)]
    assert state_from_boxes(boxes, _NAMES) == PatientState.STANDING


def test_first_box_wins_when_confidence_ties():
    boxes = [_FakeBox(cls=0, conf=0.7), _FakeBox(cls=2, conf=0.7)]
    assert state_from_boxes(boxes, _NAMES) == PatientState.IN_BED
