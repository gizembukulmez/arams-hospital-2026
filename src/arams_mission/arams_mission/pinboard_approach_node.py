"""Thin ROS wrapper: sends one NavigateToPose goal to the pinboard-viewing pose.

Runs once at startup so the robot is facing the pinboard before
tag_reader_node can lock in an AprilTag ID; the pinboard isn't guaranteed
to be in the camera's view from the spawn pose.
"""

import rclpy
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy

from arams_mission_msgs.msg import PinboardReady

from arams_mission.room_navigator import (
    OUTCOME_LOG_LEVEL,
    NavigationOutcome,
    RoomPose,
    interpret_result,
)
from arams_mission.ros_pose import pose_stamped

# Must match tag_reader_node's subscriber QoS (transient_local) so it still
# receives this even if it starts after the goal already succeeded.
_READY_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# This node fires at process startup, racing bt_navigator's own lifecycle
# activation (which can take several seconds during Nav2 bringup).
# wait_for_server() only confirms the action server is discoverable, not
# that it has finished activating, so an early goal gets a clean
# "Action server is inactive" rejection rather than an error; retry
# instead of giving up. room_navigator_node doesn't need this: it only
# sends a goal once tag_reader_node locks in a tag, by which point Nav2
# has long since finished starting up.
_RETRY_PERIOD_SEC = 1.0
_MAX_ATTEMPTS = 30


class PinboardApproachNode(Node):
    """Sends one NavigateToPose goal to the pinboard-viewing pose."""

    def __init__(self) -> None:
        super().__init__('pinboard_approach_node')

        self._pose = self._load_pinboard_pose()
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._ready_pub = self.create_publisher(PinboardReady, 'pinboard_ready', _READY_QOS)
        self._attempts = 0
        self._retry_timer = None
        self._send_goal()

    def _load_pinboard_pose(self) -> RoomPose:
        self.declare_parameter('x', 0.0)
        self.declare_parameter('y', 0.0)
        self.declare_parameter('yaw', 0.0)
        return RoomPose(
            x=self.get_parameter('x').value,
            y=self.get_parameter('y').value,
            yaw_rad=self.get_parameter('yaw').value,
        )

    def _send_goal(self) -> None:
        self._attempts += 1
        goal = NavigateToPose.Goal()
        goal.pose = pose_stamped(self._pose, self.get_clock().now().to_msg())
        self.get_logger().info(
            f'Sending navigation goal to pinboard pose (attempt {self._attempts}): {self._pose}')

        self._action_client.wait_for_server()
        send_goal_future = self._action_client.send_goal_async(goal)
        send_goal_future.add_done_callback(self._on_goal_response)

    def _on_goal_response(self, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self._handle_rejection()
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_result)

    def _handle_rejection(self) -> None:
        if self._attempts >= _MAX_ATTEMPTS:
            self._report(NavigationOutcome.REJECTED, 'Nav2 rejected the pinboard approach goal')
            return
        self.get_logger().warn(
            f'Pinboard approach goal rejected (attempt {self._attempts}/{_MAX_ATTEMPTS}): '
            'Nav2 is likely still activating, retrying shortly.')
        self._retry_timer = self.create_timer(_RETRY_PERIOD_SEC, self._retry)

    def _retry(self) -> None:
        self._retry_timer.cancel()
        self._send_goal()

    def _on_result(self, future) -> None:
        status = future.result().status
        outcome = interpret_result(status)
        self._report(outcome, f'NavigateToPose finished with status {status}')

    def _report(self, outcome: NavigationOutcome, detail: str) -> None:
        log = getattr(self.get_logger(), OUTCOME_LOG_LEVEL[outcome])
        log(f'Pinboard approach outcome: {outcome.name} ({detail})')
        # Only a confirmed arrival may unblock tag_reader_node; on any other
        # outcome the mission stays stalled here rather than reading tags
        # from a pose we never actually reached.
        if outcome == NavigationOutcome.SUCCEEDED:
            self._ready_pub.publish(PinboardReady())


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = PinboardApproachNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
