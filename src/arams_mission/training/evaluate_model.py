#!/usr/bin/env python3
"""Evaluates models/best.pt against the held-out val set named in data.yaml.

Run outside ROS, same environment as train_yolo.py (`pip install ultralytics`).
Prints per-class accuracy, a report to read, not a pass/fail gate. Revisit
once there's a sense of what's normal, given the current class imbalance
(in_bed=59, on_floor=101, standing=42 across train+val; see
arams_mission/README.md).
"""

from pathlib import Path

import cv2
import yaml

from arams_mission.patient_detector import PatientDetector, PatientState

_TRAINING_DIR = Path(__file__).resolve().parent
_DATA_YAML = _TRAINING_DIR / 'data.yaml'
_WEIGHTS_PATH = _TRAINING_DIR.parent / 'models' / 'best.pt'


def _ground_truth_state(label_path: Path, names: dict[int, str]) -> PatientState:
    first_line = label_path.read_text().splitlines()[0]
    class_id = int(first_line.split()[0])
    return PatientState(names[class_id])


def main() -> None:
    data = yaml.safe_load(_DATA_YAML.read_text())
    dataset_path = Path(data['path'])
    images_dir = dataset_path / data['val']
    labels_dir = dataset_path / 'labels' / 'val'

    if not images_dir.is_dir():
        raise FileNotFoundError(
            f"{images_dir} doesn't exist, check data.yaml's path: matches where "
            "the labeled dataset actually lives on this machine.")

    detector = PatientDetector(str(_WEIGHTS_PATH))

    correct = {state: 0 for state in PatientState}
    total = {state: 0 for state in PatientState}
    misclassified = []

    for image_path in sorted(images_dir.glob('*.jpg')):
        label_path = labels_dir / f'{image_path.stem}.txt'
        if not label_path.exists():
            continue

        expected = _ground_truth_state(label_path, data['names'])
        predicted = detector.detect(cv2.imread(str(image_path)))

        total[expected] += 1
        if predicted == expected:
            correct[expected] += 1
        else:
            misclassified.append((image_path.name, expected, predicted))

    print(f'Weights: {_WEIGHTS_PATH}')
    print(f'Dataset: {images_dir}\n')
    for state in PatientState:
        n = total[state]
        accuracy = correct[state] / n if n else float('nan')
        print(f'{state.value:>10}: {correct[state]:>3}/{n:<3} correct ({accuracy:.0%})')

    if misclassified:
        print('\nMisclassified:')
        for filename, expected, predicted in misclassified:
            got = predicted.value if predicted is not None else 'no detection'
            print(f'  {filename}: expected {expected.value}, got {got}')


if __name__ == '__main__':
    main()
