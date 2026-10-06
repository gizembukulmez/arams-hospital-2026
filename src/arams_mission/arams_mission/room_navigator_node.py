"""Thin ROS wrapper around RoomNavigator: sends a NavigateToPose goal for a commanded room."""

import rclpy
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy

from arams_mission_msgs.msg import MissionTarget, NavigationResult

from arams_mission.room_navigator import (
    OUTCOME_LOG_LEVEL,
    NavigationOutcome,
    RoomNavigator,
    RoomPose,
)
from arams_mission.ros_pose import pose_stamped
from arams_mission.trial_outcome_logger import TrialOutcomeLogger

# Must match orchestrator_node's publisher QoS (volatile); navigate_command
# is a one-time imperative, not a fact worth latching for late joiners.
_COMMAND_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.VOLATILE,
)

_OUTCOME_TO_RESULT_MSG = {
    NavigationOutcome.SUCCEEDED: NavigationResult.SUCCEEDED,
    NavigationOutcome.ABORTED: NavigationResult.ABORTED,
    NavigationOutcome.CANCELED: NavigationResult.CANCELED,
    NavigationOutcome.REJECTED: NavigationResult.REJECTED,
    NavigationOutcome.UNKNOWN_ROOM: NavigationResult.UNKNOWN_ROOM,
}


class RoomNavigatorNode(Node):
    """Sends a NavigateToPose goal for the room named by /navigate_command."""

    def __init__(self) -> None:
        super().__init__('room_navigator_node')

        _, room_poses = self._load_room_poses()
        self._navigator = RoomNavigator(room_poses)
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._target_locked = False
        self._room_id = None

        self.declare_parameter('trial_log_path', '')
        trial_log_path = self.get_parameter('trial_log_path').value
        self._trial_logger = TrialOutcomeLogger(trial_log_path) if trial_log_path else None

        self._result_pub = self.create_publisher(NavigationResult, 'navigation_result', 1)
        self.create_subscription(
            MissionTarget, 'navigate_command', self._on_navigate_command, _COMMAND_QOS)

    def _load_room_poses(self) -> tuple[list[int], dict[int, RoomPose]]:
        self.declare_parameter('room_ids', [1, 2, 3])
        room_ids = self.get_parameter('room_ids').value

        room_poses = {}
        for room_id in room_ids:
            self.declare_parameter(f'room_{room_id}.x', 0.0)
            self.declare_parameter(f'room_{room_id}.y', 0.0)
            self.declare_parameter(f'room_{room_id}.yaw', 0.0)
            room_poses[room_id] = RoomPose(
                x=self.get_parameter(f'room_{room_id}.x').value,
                y=self.get_parameter(f'room_{room_id}.y').value,
                yaw_rad=self.get_parameter(f'room_{room_id}.yaw').value,
            )
        return room_ids, room_poses

    def _on_navigate_command(self, msg: MissionTarget) -> None:
        if self._target_locked:
            return

        self._room_id = msg.room_id
        room_pose = self._navigator.pose_for_room(msg.room_id)
        if room_pose is None:
            self._report(
                NavigationOutcome.UNKNOWN_ROOM, f'room {msg.room_id} has no configured pose')
            return

        self._target_locked = True
        self._send_navigation_goal(room_pose)

    def _send_navigation_goal(self, room_pose: RoomPose) -> None:
        goal = NavigateToPose.Goal()
        goal.pose = pose_stamped(room_pose, self.get_clock().now().to_msg())
        self.get_logger().info(f'Sending navigation goal for room {self._room_id}: {room_pose}')

        self._action_client.wait_for_server()
        send_goal_future = self._action_client.send_goal_async(
            goal, feedback_callback=self._on_feedback)
        send_goal_future.add_done_callback(self._on_goal_response)

    def _on_goal_response(self, future) -> None:
        goal_handle = future.result()
        if not goal_handle.accepted:
            self._report(NavigationOutcome.REJECTED, 'Nav2 rejected the navigation goal')
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_result)

    def _on_feedback(self, feedback_msg) -> None:
        self.get_logger().info(
            f'Distance remaining: {feedback_msg.feedback.distance_remaining:.2f} m',
            throttle_duration_sec=2.0)

    def _on_result(self, future) -> None:
        status = future.result().status
        outcome = self._navigator.interpret_result(status)
        self._report(outcome, f'NavigateToPose finished with status {status}')

    def _report(self, outcome: NavigationOutcome, detail: str) -> None:
        log = getattr(self.get_logger(), OUTCOME_LOG_LEVEL[outcome])
        log(f'Navigation outcome: {outcome.name} ({detail})')
        if self._trial_logger is not None:
            self._trial_logger.log(self._room_id, outcome, detail)
        self._result_pub.publish(NavigationResult(
            outcome=_OUTCOME_TO_RESULT_MSG[outcome], room_id=self._room_id, detail=detail))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RoomNavigatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
