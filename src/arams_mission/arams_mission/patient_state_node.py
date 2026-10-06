"""Thin ROS wrapper around PatientDetector: classifies each camera frame, publishes the state."""

import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

from arams_mission_msgs.msg import PatientState as PatientStateMsg

from arams_mission.patient_detector import PatientDetector, PatientState

_STATE_TO_MSG = {
    PatientState.IN_BED: PatientStateMsg.IN_BED,
    PatientState.ON_FLOOR: PatientStateMsg.ON_FLOOR,
    PatientState.STANDING: PatientStateMsg.STANDING,
}


class PatientStateNode(Node):
    """Publishes the patient's classified state for confident detections, rate-limited.

    Skips inference entirely while nothing is subscribed to /patient_state
    (orchestrator_node only subscribes once DETECT starts). YOLO is the
    heaviest thing running during tag reading and navigation; running it
    unconsumed for the whole mission wastes CPU that Nav2's control loop
    and Webots' physics stepping need, worst of all on machines with no
    GPU to offload it to.
    """

    def __init__(self) -> None:
        super().__init__('patient_state_node')

        self.declare_parameter('camera_topic', '/camera/image_raw')
        self.declare_parameter('weights_path', 'best.pt')
        # YOLO inference is CPU-heavy; running it on every camera frame competes
        # with Nav2's control loop and Webots' physics stepping for CPU and can
        # visibly stall the sim. 2Hz is plenty for a state that doesn't change
        # frame-to-frame.
        self.declare_parameter('min_period_sec', 0.5)
        camera_topic = self.get_parameter('camera_topic').value
        weights_path = self.get_parameter('weights_path').value
        self._min_period_sec = self.get_parameter('min_period_sec').value

        self._detector = PatientDetector(weights_path)
        self._bridge = CvBridge()
        self._state_pub = self.create_publisher(PatientStateMsg, 'patient_state', 10)
        self._last_processed_time = None
        self.create_subscription(Image, camera_topic, self._on_image, 10)

    def _on_image(self, msg: Image) -> None:
        if self._state_pub.get_subscription_count() == 0:
            return

        now = self.get_clock().now()
        if self._last_processed_time is not None:
            elapsed_sec = (now - self._last_processed_time).nanoseconds / 1e9
            if elapsed_sec < self._min_period_sec:
                return
        self._last_processed_time = now

        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        state = self._detector.detect(frame)
        if state is None:
            return

        self._state_pub.publish(PatientStateMsg(state=_STATE_TO_MSG[state]))
        self.get_logger().info(f'Detected patient state: {state.value}', throttle_duration_sec=2.0)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = PatientStateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
