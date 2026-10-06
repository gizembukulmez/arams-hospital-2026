"""Thin ROS wrapper around PinboardTagReader: subscribes to detections, publishes the target."""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy

from apriltag_msgs.msg import AprilTagDetectionArray
from arams_mission_msgs.msg import MissionTarget, PinboardReady

from arams_mission.pinboard_tag_reader import PinboardTagReader

# Latched: used both for the incoming pinboard_ready signal (so we don't
# miss it if pinboard_approach_node succeeds before this node starts) and
# the outgoing mission_target (so a node that starts after lock-in, a
# manual `ros2 topic echo`, or the orchestrator, still gets it).
_LATCHED_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class TagReaderNode(Node):
    """Publishes the pinboard's AprilTag ID as the mission target, once locked in."""

    def __init__(self) -> None:
        super().__init__('tag_reader_node')

        self.declare_parameter('valid_ids', [1, 2, 3])
        self.declare_parameter('required_consistent_detections', 5)

        valid_ids = set(self.get_parameter('valid_ids').value)
        required_consistent_detections = self.get_parameter(
            'required_consistent_detections').value
        self._reader = PinboardTagReader(valid_ids, required_consistent_detections)

        self._target_pub = self.create_publisher(MissionTarget, 'mission_target', _LATCHED_QOS)
        self._published = False
        # Detection doesn't start until pinboard_approach_node confirms
        # arrival; otherwise the camera can lock onto a door's own
        # AprilTag (same family, same 1-3 ID range) while still turning
        # toward the pinboard.
        self._detections_sub = None
        self.create_subscription(
            PinboardReady, 'pinboard_ready', self._on_pinboard_ready, _LATCHED_QOS)

    def _on_pinboard_ready(self, msg: PinboardReady) -> None:
        if self._detections_sub is not None:
            return
        self.get_logger().info('Pinboard reached, starting tag detection.')
        self._detections_sub = self.create_subscription(
            AprilTagDetectionArray, 'detections', self._on_detections, 1)

    def _on_detections(self, msg: AprilTagDetectionArray) -> None:
        detected_ids = [detection.id for detection in msg.detections]
        locked_id = self._reader.observe(detected_ids)
        if locked_id is not None and not self._published:
            self._published = True
            self._target_pub.publish(MissionTarget(room_id=locked_id))
            self.get_logger().info(f'Locked pinboard tag ID {locked_id} as mission target')


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = TagReaderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
