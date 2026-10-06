"""Smoke test for the real trained model: proves the handoff actually loads
and runs, not that it's accurate. See training/evaluate_model.py for that.
"""

import importlib.util
from pathlib import Path

import cv2
import pytest

from arams_mission.patient_detector import PatientDetector, PatientState

# pytest.importorskip() at module level mis-collects sibling test files under
# this repo's ament pytest plugin stack (verified: it silently drops every
# other test file in the same session); skipif avoids that failure mode.
pytestmark = pytest.mark.skipif(
    importlib.util.find_spec('ultralytics') is None, reason='ultralytics not installed')

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_WEIGHTS_PATH = _PACKAGE_ROOT / 'models' / 'best.pt'
_FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'


@pytest.fixture(scope='module')
def detector():
    return PatientDetector(str(_WEIGHTS_PATH))


@pytest.mark.parametrize('fixture_filename', [
    'in_bed_sample.jpg',
    'on_floor_sample.jpg',
    'standing_sample.jpg',
])
def test_detect_returns_a_state_for_each_class_sample(detector, fixture_filename):
    frame = cv2.imread(str(_FIXTURES_DIR / fixture_filename))
    assert frame is not None

    state = detector.detect(frame)

    assert isinstance(state, PatientState)
