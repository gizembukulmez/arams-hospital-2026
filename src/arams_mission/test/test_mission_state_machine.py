import pytest

from arams_mission.mission_state_machine import MissionState, MissionStateMachine
from arams_mission.patient_detector import PatientState
from arams_mission.room_navigator import NavigationOutcome


def make_sm(**kwargs):
    return MissionStateMachine(known_room_ids={1, 2, 3}, **kwargs)


def arrive_at_room(sm, room_id=1):
    sm.on_mission_target(room_id)
    sm.on_door_result(True, 'opened')
    sm.on_navigation_result(NavigationOutcome.SUCCEEDED, 'arrived')


def test_starts_in_read_tag():
    sm = make_sm()
    assert sm.state == MissionState.READ_TAG


def test_mission_target_moves_to_open_door():
    sm = make_sm()
    sm.on_mission_target(2)
    assert sm.state == MissionState.OPEN_DOOR
    assert sm.room_id == 2


def test_unknown_room_fails_immediately():
    sm = make_sm()
    sm.on_mission_target(99)
    assert sm.state == MissionState.REPORT
    assert sm.result.success is False
    assert sm.result.failed_stage == MissionState.OPEN_DOOR


def test_read_tag_timeout_fails():
    sm = make_sm()
    sm.on_read_tag_timeout()
    assert sm.state == MissionState.REPORT
    assert sm.result.failed_stage == MissionState.READ_TAG


def test_read_tag_timeout_after_lock_in_is_ignored():
    sm = make_sm()
    sm.on_mission_target(1)
    sm.on_read_tag_timeout()
    assert sm.state == MissionState.OPEN_DOOR


def test_door_success_moves_to_navigate():
    sm = make_sm()
    sm.on_mission_target(1)
    sm.on_door_result(True, 'opened')
    assert sm.state == MissionState.NAVIGATE


def test_door_failure_retries_before_failing():
    sm = make_sm(door_open_max_attempts=2)
    sm.on_mission_target(1)
    sm.on_door_result(False, 'stuck')
    assert sm.state == MissionState.OPEN_DOOR


def test_door_failure_exhausting_attempts_fails_the_mission():
    sm = make_sm(door_open_max_attempts=2)
    sm.on_mission_target(1)
    sm.on_door_result(False, 'stuck')
    sm.on_door_result(False, 'stuck again')
    assert sm.state == MissionState.REPORT
    assert sm.result.failed_stage == MissionState.OPEN_DOOR
    assert sm.result.detail == 'stuck again'


def test_navigation_success_moves_to_detect():
    sm = make_sm()
    arrive_at_room(sm)
    assert sm.state == MissionState.DETECT


@pytest.mark.parametrize('outcome', [
    NavigationOutcome.ABORTED,
    NavigationOutcome.CANCELED,
    NavigationOutcome.REJECTED,
    NavigationOutcome.UNKNOWN_ROOM,
])
def test_navigation_failure_outcomes_fail_the_mission(outcome):
    sm = make_sm()
    sm.on_mission_target(1)
    sm.on_door_result(True, 'opened')
    sm.on_navigation_result(outcome, 'failed')
    assert sm.state == MissionState.REPORT
    assert sm.result.failed_stage == MissionState.NAVIGATE


def test_patient_state_settles_after_enough_observations():
    sm = make_sm(detect_settle_count=3)
    arrive_at_room(sm)
    sm.on_patient_state(PatientState.IN_BED)
    sm.on_patient_state(PatientState.IN_BED)
    assert sm.state == MissionState.DETECT
    sm.on_patient_state(PatientState.IN_BED)
    assert sm.state == MissionState.REPORT
    assert sm.result.success is True
    assert sm.result.patient_state == PatientState.IN_BED


def test_patient_state_majority_wins_over_a_minority_reading():
    sm = make_sm(detect_settle_count=3)
    arrive_at_room(sm)
    sm.on_patient_state(PatientState.ON_FLOOR)
    sm.on_patient_state(PatientState.STANDING)
    sm.on_patient_state(PatientState.STANDING)
    assert sm.result.patient_state == PatientState.STANDING


def test_detect_timeout_with_no_observations_fails():
    sm = make_sm()
    arrive_at_room(sm)
    sm.on_detect_timeout()
    assert sm.state == MissionState.REPORT
    assert sm.result.success is False
    assert sm.result.failed_stage == MissionState.DETECT


def test_detect_timeout_with_a_partial_window_still_succeeds():
    sm = make_sm(detect_settle_count=3)
    arrive_at_room(sm)
    sm.on_patient_state(PatientState.STANDING)
    sm.on_detect_timeout()
    assert sm.state == MissionState.REPORT
    assert sm.result.success is True
    assert sm.result.patient_state == PatientState.STANDING


def test_acknowledge_report_moves_to_done():
    sm = make_sm()
    sm.on_read_tag_timeout()
    assert sm.state == MissionState.REPORT
    sm.acknowledge_report()
    assert sm.state == MissionState.DONE


def test_door_result_before_mission_target_is_ignored():
    sm = make_sm()
    sm.on_door_result(True, 'opened')
    assert sm.state == MissionState.READ_TAG


def test_navigation_result_before_door_opens_is_ignored():
    sm = make_sm()
    sm.on_navigation_result(NavigationOutcome.SUCCEEDED, 'x')
    assert sm.state == MissionState.READ_TAG


def test_patient_state_before_navigation_succeeds_is_ignored():
    sm = make_sm()
    sm.on_mission_target(1)
    sm.on_patient_state(PatientState.IN_BED)
    assert sm.state == MissionState.OPEN_DOOR


def test_mission_target_after_done_is_ignored():
    sm = make_sm()
    sm.on_read_tag_timeout()
    sm.acknowledge_report()
    sm.on_mission_target(1)
    assert sm.state == MissionState.DONE
