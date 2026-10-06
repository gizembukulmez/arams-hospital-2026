#!/usr/bin/env python3
"""Fine-tunes YOLOv8n on the 3 patient-state classes (in_bed / on_floor / standing).

Run outside ROS, in a plain Python environment (`pip install ultralytics`),
after labeling a dataset per data.yaml. Produces
runs/detect/train/weights/best.pt. Point patient_state.yaml's weights_path
at that file once training is done.
"""

from ultralytics import YOLO


def main() -> None:
    # Fine-tuning a COCO-pretrained nano model needs far less data and time
    # than training from scratch, which is what makes a few hundred labeled
    # frames enough for this task.
    model = YOLO('yolov8n.pt')

    model.train(
        data='data.yaml',
        epochs=100,
        imgsz=640,
        batch=16,
        patience=20,  # stop early if validation score hasn't improved in 20 epochs
        project='runs/detect',
        name='train',
    )

    metrics = model.val()
    print(metrics)


if __name__ == '__main__':
    main()
