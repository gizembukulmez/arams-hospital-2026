"""Decides which room pose to send Nav2 to and interprets the result.

Plain Python, no ROS: keeps application logic out of ROS nodes.
"""

import math
from dataclasses import dataclass
from enum import Enum, auto

# Mirrors action_msgs/msg/GoalStatus's wire values, so this module can
# interpret a NavigateToPose result from a plain int without importing
# any ROS message type.
_STATUS_SUCCEEDED = 4
_STATUS_CANCELED = 5
_STATUS_ABORTED = 6


@dataclass
class RoomPose:
    """A room's approach pose in the map frame."""

    x: float
    y: float
    yaw_rad: float


class NavigationOutcome(Enum):
    """Terminal outcome of a room navigation attempt."""

    SUCCEEDED = auto()
    ABORTED = auto()
    CANCELED = auto()
    REJECTED = auto()
    UNKNOWN_ROOM = auto()


# Shared by any node that reports a NavigationOutcome to the ROS logger;
# only SUCCEEDED is worth an INFO line, everything else needs attention.
OUTCOME_LOG_LEVEL = {
    NavigationOutcome.SUCCEEDED: 'info',
    NavigationOutcome.ABORTED: 'error',
    NavigationOutcome.CANCELED: 'error',
    NavigationOutcome.REJECTED: 'error',
    NavigationOutcome.UNKNOWN_ROOM: 'error',
}


def interpret_result(status: int) -> NavigationOutcome:
    """Map a NavigateToPose terminal status to a NavigationOutcome.

    Any status other than the known succeeded/canceled values is treated
    as ABORTED: an unrecognized terminal status is a failure, not a
    success. Shared by any node that sends a single NavigateToPose goal
    and needs to classify its result (RoomNavigator, PinboardApproachNode).
    """
    if status == _STATUS_SUCCEEDED:
        return NavigationOutcome.SUCCEEDED
    if status == _STATUS_CANCELED:
        return NavigationOutcome.CANCELED
    return NavigationOutcome.ABORTED


class RoomNavigator:
    """Looks up a room's target pose and classifies a navigation result."""

    def __init__(self, room_poses: dict[int, RoomPose]) -> None:
        self._room_poses = room_poses

    def pose_for_room(self, room_id: int) -> RoomPose | None:
        """Return the room's target pose, or None if room_id is unknown."""
        return self._room_poses.get(room_id)

    def interpret_result(self, status: int) -> NavigationOutcome:
        """Map a NavigateToPose terminal status to a NavigationOutcome."""
        return interpret_result(status)


def yaw_to_quaternion_z_w(yaw_rad: float) -> tuple[float, float]:
    """Convert a yaw angle (radians, about z) to a quaternion's (z, w).

    x and y are always 0 for a rotation about z alone.
    """
    return math.sin(yaw_rad / 2.0), math.cos(yaw_rad / 2.0)
