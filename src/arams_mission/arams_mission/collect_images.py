"""Dev tool: saves camera frames to disk for building the patient-state training set.

Not part of the graded mission flow; run manually while teleoperating the
robot around a patient in each of the three states.
"""

import os

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image


class ImageCollectorNode(Node):
    """Saves every Nth camera frame to `save_dir` for later labeling."""

    def __init__(self) -> None:
        super().__init__('image_collector')

        self.declare_parameter('camera_topic', '/camera/image_raw')
        self.declare_parameter('save_dir', os.path.expanduser('~/arams_dataset/raw'))
        self.declare_parameter('capture_period_frames', 10)

        self._save_dir = self.get_parameter('save_dir').value
        self._capture_period_frames = self.get_parameter('capture_period_frames').value
        os.makedirs(self._save_dir, exist_ok=True)

        self._bridge = CvBridge()
        self._frame_count = 0
        self._saved_count = 0

        camera_topic = self.get_parameter('camera_topic').value
        self.create_subscription(Image, camera_topic, self._on_image, 10)
        self.get_logger().info(f'Saving frames from {camera_topic} to {self._save_dir}')

    def _on_image(self, msg: Image) -> None:
        self._frame_count += 1
        if self._frame_count % self._capture_period_frames != 0:
            return

        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        filename = os.path.join(self._save_dir, f'frame_{self._saved_count:05d}.jpg')
        cv2.imwrite(filename, frame)
        self._saved_count += 1
        self.get_logger().info(f'Saved {filename}', throttle_duration_sec=1.0)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ImageCollectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
