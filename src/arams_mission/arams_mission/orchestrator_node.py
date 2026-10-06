"""Thin ROS wrapper around MissionStateMachine: sequences the mission end to end.

DoorClient.open_door_async() blocks on wait_for_service() with no timeout, since
this node runs a SingleThreadedExecutor (like every node in this package), a door
service that never appears would hang the executor before any timer or retry logic
here could run. Doors are part of the prelaunched world and should already exist
by OPEN_DOOR, so this is a documented, accepted risk rather than something handled.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy

from arams_mission_msgs.msg import MissionReport, MissionTarget, NavigationResult
from arams_mission_msgs.msg import PatientState as PatientStateMsg

from arams_mission.door_client import DoorClient
from arams_mission.mission_state_machine import MissionState, MissionStateMachine
from arams_mission.patient_detector import PatientState
from arams_mission.room_navigator import NavigationOutcome

# Must match tag_reader_node's publisher QoS (transient_local) so this node
# still receives the mission target even if it starts after lock-in.
_TARGET_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# The final mission result, latched so a late-joining consumer (a grading
# script, a manual `ros2 topic echo`) still gets it, matching mission_target
# and pinboard_ready's own latched, publish-once pattern.
_REPORT_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

_RESULT_MSG_TO_OUTCOME = {
    NavigationResult.SUCCEEDED: NavigationOutcome.SUCCEEDED,
    NavigationResult.ABORTED: NavigationOutcome.ABORTED,
    NavigationResult.CANCELED: NavigationOutcome.CANCELED,
    NavigationResult.REJECTED: NavigationOutcome.REJECTED,
    NavigationResult.UNKNOWN_ROOM: NavigationOutcome.UNKNOWN_ROOM,
}

_MSG_TO_PATIENT_STATE = {
    PatientStateMsg.IN_BED: PatientState.IN_BED,
    PatientStateMsg.ON_FLOOR: PatientState.ON_FLOOR,
    PatientStateMsg.STANDING: PatientState.STANDING,
}

_PATIENT_STATE_TO_MSG = {value: key for key, value in _MSG_TO_PATIENT_STATE.items()}

_FAILED_STAGE_TO_MSG = {
    MissionState.READ_TAG: MissionReport.READ_TAG,
    MissionState.OPEN_DOOR: MissionReport.OPEN_DOOR,
    MissionState.NAVIGATE: MissionReport.NAVIGATE,
    MissionState.DETECT: MissionReport.DETECT,
}


class OrchestratorNode(Node):
    """Sequences the mission: read tag -> open door -> navigate -> detect -> report."""

    def __init__(self) -> None:
        super().__init__('orchestrator_node')

        self.declare_parameter('room_ids', [1, 2, 3])
        self.declare_parameter('read_tag_timeout_sec', 60.0)
        self.declare_parameter('detect_timeout_sec', 30.0)
        self.declare_parameter('door_open_max_attempts', 2)
        self.declare_parameter('detect_settle_count', 3)

        room_ids = self.get_parameter('room_ids').value
        self._detect_timeout_sec = self.get_parameter('detect_timeout_sec').value

        self._sm = MissionStateMachine(
            known_room_ids=set(room_ids),
            door_open_max_attempts=self.get_parameter('door_open_max_attempts').value,
            detect_settle_count=self.get_parameter('detect_settle_count').value,
        )
        self._door_client = DoorClient(self, room_ids)

        self._command_pub = self.create_publisher(MissionTarget, 'navigate_command', 1)
        self._report_pub = self.create_publisher(MissionReport, 'mission_report', _REPORT_QOS)
        self._patient_state_sub = None
        self._detect_timer = None

        self.create_subscription(
            MissionTarget, 'mission_target', self._on_mission_target, _TARGET_QOS)
        self.create_subscription(
            NavigationResult, 'navigation_result', self._on_navigation_result, 1)

        read_tag_timeout_sec = self.get_parameter('read_tag_timeout_sec').value
        self._read_tag_timer = self.create_timer(read_tag_timeout_sec, self._on_read_tag_timeout)

    def _on_mission_target(self, msg: MissionTarget) -> None:
        self._read_tag_timer.cancel()
        self._sm.on_mission_target(msg.room_id)
        self._dispatch()

    def _on_read_tag_timeout(self) -> None:
        self._read_tag_timer.cancel()
        self._sm.on_read_tag_timeout()
        self._dispatch()

    def _on_door_response(self, future) -> None:
        response = future.result()
        self._sm.on_door_result(response.success, response.message)
        self._dispatch()

    def _on_navigation_result(self, msg: NavigationResult) -> None:
        self._sm.on_navigation_result(_RESULT_MSG_TO_OUTCOME[msg.outcome], msg.detail)
        self._dispatch()

    def _on_patient_state(self, msg: PatientStateMsg) -> None:
        self._sm.on_patient_state(_MSG_TO_PATIENT_STATE[msg.state])
        self._dispatch()

    def _on_detect_timeout(self) -> None:
        self._detect_timer.cancel()
        self._sm.on_detect_timeout()
        self._dispatch()

    def _dispatch(self) -> None:
        if self._sm.state is MissionState.OPEN_DOOR:
            self._open_door()
        elif self._sm.state is MissionState.NAVIGATE:
            self._command_pub.publish(MissionTarget(room_id=self._sm.room_id))
        elif self._sm.state is MissionState.DETECT and self._patient_state_sub is None:
            self._start_detect()
        elif self._sm.state is MissionState.REPORT:
            self._publish_report()
            self._sm.acknowledge_report()

    def _open_door(self) -> None:
        self.get_logger().info(f'Opening door for room {self._sm.room_id}')
        door_future = self._door_client.open_door_async(self._sm.room_id)
        door_future.add_done_callback(self._on_door_response)

    def _start_detect(self) -> None:
        self.get_logger().info('Arrived, starting patient-state detection.')
        self._patient_state_sub = self.create_subscription(
            PatientStateMsg, 'patient_state', self._on_patient_state, 10)
        self._detect_timer = self.create_timer(self._detect_timeout_sec, self._on_detect_timeout)

    def _publish_report(self) -> None:
        result = self._sm.result
        report = MissionReport(
            success=result.success,
            room_id=result.room_id if result.room_id is not None else -1,
            patient_state_known=result.patient_state is not None,
            detail=result.detail,
        )
        if result.failed_stage is not None:
            report.failed_stage = _FAILED_STAGE_TO_MSG[result.failed_stage]
        if result.patient_state is not None:
            report.patient_state = PatientStateMsg(
                state=_PATIENT_STATE_TO_MSG[result.patient_state])
        self._report_pub.publish(report)

        log = self.get_logger().info if result.success else self.get_logger().error
        outcome = 'succeeded' if result.success else 'failed'
        log(f'Mission {outcome}: {result.detail}')


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = OrchestratorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
