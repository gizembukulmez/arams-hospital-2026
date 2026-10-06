import math

import pytest

from arams_mission.room_navigator import (
    NavigationOutcome,
    RoomNavigator,
    RoomPose,
    yaw_to_quaternion_z_w,
)


def make_navigator():
    return RoomNavigator({
        1: RoomPose(x=-5.26, y=3.0, yaw_rad=1.5708),
        2: RoomPose(x=0.0, y=3.0, yaw_rad=1.5708),
        3: RoomPose(x=5.26, y=3.0, yaw_rad=1.5708),
    })


def test_pose_for_known_room():
    navigator = make_navigator()
    assert navigator.pose_for_room(2) == RoomPose(x=0.0, y=3.0, yaw_rad=1.5708)


def test_pose_for_unknown_room_is_none():
    navigator = make_navigator()
    assert navigator.pose_for_room(99) is None


def test_interpret_result_succeeded():
    navigator = make_navigator()
    assert navigator.interpret_result(4) == NavigationOutcome.SUCCEEDED


def test_interpret_result_aborted():
    navigator = make_navigator()
    assert navigator.interpret_result(6) == NavigationOutcome.ABORTED


def test_interpret_result_canceled():
    navigator = make_navigator()
    assert navigator.interpret_result(5) == NavigationOutcome.CANCELED


def test_interpret_result_unknown_status_is_treated_as_aborted():
    navigator = make_navigator()
    assert navigator.interpret_result(99) == NavigationOutcome.ABORTED


def test_yaw_zero():
    z, w = yaw_to_quaternion_z_w(0.0)
    assert z == pytest.approx(0.0)
    assert w == pytest.approx(1.0)


def test_yaw_pi():
    z, w = yaw_to_quaternion_z_w(math.pi)
    assert z == pytest.approx(1.0)
    assert w == pytest.approx(0.0, abs=1e-9)


def test_yaw_half_pi():
    z, w = yaw_to_quaternion_z_w(math.pi / 2)
    assert z == pytest.approx(math.sqrt(2) / 2)
    assert w == pytest.approx(math.sqrt(2) / 2)
