"""Sequences the mission: READ_TAG -> OPEN_DOOR -> NAVIGATE -> DETECT -> REPORT -> DONE.

Plain Python, no ROS: keeps application logic out of ROS nodes.
"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto

from arams_mission.patient_detector import PatientState
from arams_mission.room_navigator import NavigationOutcome


class MissionState(Enum):
    """A stage of the mission, in the order the orchestrator moves through them."""

    READ_TAG = auto()
    OPEN_DOOR = auto()
    NAVIGATE = auto()
    DETECT = auto()
    REPORT = auto()
    DONE = auto()


@dataclass
class MissionResult:
    """The mission's final outcome, set once REPORT is entered."""

    success: bool
    room_id: int | None
    failed_stage: MissionState | None
    detail: str
    patient_state: PatientState | None


class MissionStateMachine:
    """Drives the mission's state transitions from event callbacks.

    Every `on_*` method no-ops if called outside the state it applies to: a
    stray or duplicate event (e.g. a second mission_target) shouldn't move
    the mission backward or sideways.
    """

    def __init__(
        self,
        known_room_ids: set[int],
        door_open_max_attempts: int = 2,
        detect_settle_count: int = 3,
    ) -> None:
        self._known_room_ids = known_room_ids
        self._door_open_max_attempts = door_open_max_attempts
        self._detect_settle_count = detect_settle_count

        self._state = MissionState.READ_TAG
        self._room_id: int | None = None
        self._door_attempts = 0
        self._patient_observations: list[PatientState] = []
        self._result: MissionResult | None = None

    @property
    def state(self) -> MissionState:
        return self._state

    @property
    def room_id(self) -> int | None:
        return self._room_id

    @property
    def result(self) -> MissionResult | None:
        return self._result

    def on_mission_target(self, room_id: int) -> None:
        """Lock in the target room and advance to OPEN_DOOR."""
        if self._state is not MissionState.READ_TAG:
            return
        self._room_id = room_id
        # DoorClient only holds a client per known room id; checking here,
        # not just relying on room_navigator_node's own UNKNOWN_ROOM outcome,
        # avoids a KeyError crash if config drift ever lets an out-of-range
        # room_id reach OPEN_DOOR.
        if room_id not in self._known_room_ids:
            self._fail(MissionState.OPEN_DOOR, f'no door configured for room {room_id}')
            return
        self._state = MissionState.OPEN_DOOR

    def on_read_tag_timeout(self) -> None:
        """Fail the mission if no tag locked in before the timeout."""
        if self._state is not MissionState.READ_TAG:
            return
        self._fail(MissionState.READ_TAG, 'no AprilTag locked in before the timeout')

    def on_door_result(self, success: bool, message: str) -> None:
        """Advance to NAVIGATE on success; otherwise retry once before failing."""
        if self._state is not MissionState.OPEN_DOOR:
            return
        if success:
            self._state = MissionState.NAVIGATE
            return
        self._door_attempts += 1
        if self._door_attempts < self._door_open_max_attempts:
            return
        self._fail(MissionState.OPEN_DOOR, message)

    def on_navigation_result(self, outcome: NavigationOutcome, detail: str) -> None:
        """Advance to DETECT on success; otherwise fail NAVIGATE."""
        if self._state is not MissionState.NAVIGATE:
            return
        if outcome is NavigationOutcome.SUCCEEDED:
            self._state = MissionState.DETECT
            return
        self._fail(MissionState.NAVIGATE, detail)

    def on_patient_state(self, state: PatientState) -> None:
        """Collect one observation; report the majority once enough have settled."""
        if self._state is not MissionState.DETECT:
            return
        self._patient_observations.append(state)
        if len(self._patient_observations) < self._detect_settle_count:
            return
        self._succeed_with_patient_state(
            f'settled from {len(self._patient_observations)} observations')

    def on_detect_timeout(self) -> None:
        """Report the majority of whatever was observed, or fail if nothing was."""
        if self._state is not MissionState.DETECT:
            return
        if not self._patient_observations:
            self._fail(MissionState.DETECT, 'no patient state observed before the timeout')
            return
        self._succeed_with_patient_state(
            f'settled from {len(self._patient_observations)}/{self._detect_settle_count} '
            'observations before the timeout')

    def acknowledge_report(self) -> None:
        """Move from REPORT to the terminal DONE state."""
        if self._state is not MissionState.REPORT:
            return
        self._state = MissionState.DONE

    def _succeed_with_patient_state(self, detail: str) -> None:
        majority = Counter(self._patient_observations).most_common(1)[0][0]
        self._result = MissionResult(
            success=True,
            room_id=self._room_id,
            failed_stage=None,
            detail=detail,
            patient_state=majority,
        )
        self._state = MissionState.REPORT

    def _fail(self, stage: MissionState, detail: str) -> None:
        self._result = MissionResult(
            success=False,
            room_id=self._room_id,
            failed_stage=stage,
            detail=detail,
            patient_state=None,
        )
        self._state = MissionState.REPORT
