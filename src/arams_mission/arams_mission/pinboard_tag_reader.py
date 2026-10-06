"""Determines the pinboard's AprilTag ID from a stream of per-frame detections.

Plain Python, no ROS: keeps application logic out of ROS nodes.
"""


class PinboardTagReader:
    """Locks in the pinboard's AprilTag ID once it's seen consistently.

    A single frame's detection can be wrong (motion blur, partial view, or
    another tag such as a door marker briefly in frame), so we don't trust
    any one reading. We only lock in an ID once it's the *only* valid ID
    reported for several frames in a row; any other valid ID, or a frame
    with none of them, resets the count.
    """

    def __init__(self, valid_ids: set[int], required_consistent_detections: int) -> None:
        self._valid_ids = valid_ids
        self._required_consistent_detections = required_consistent_detections
        self._candidate_id: int | None = None
        self._consecutive_count = 0
        self._locked_id: int | None = None

    def observe(self, detected_ids: list[int]) -> int | None:
        """Feed one frame's detected tag IDs.

        Returns the locked-in ID once `required_consistent_detections`
        consecutive frames agree on the same valid ID, else None. Once
        locked, keeps returning that ID regardless of later frames.
        """
        if self._locked_id is not None:
            return self._locked_id

        frame_id = self._single_valid_id(detected_ids)
        if frame_id == self._candidate_id and frame_id is not None:
            self._consecutive_count += 1
        else:
            self._candidate_id = frame_id
            self._consecutive_count = 1 if frame_id is not None else 0

        if self._consecutive_count >= self._required_consistent_detections:
            self._locked_id = self._candidate_id

        return self._locked_id

    def _single_valid_id(self, detected_ids: list[int]) -> int | None:
        """Return the frame's valid ID, or None if zero or more than one is present.

        More than one valid ID in a single frame means the pinboard and a
        door tag (or two door tags) are both in view, too ambiguous to
        count as a reading either way.
        """
        seen = {tag_id for tag_id in detected_ids if tag_id in self._valid_ids}
        if len(seen) == 1:
            return next(iter(seen))
        return None
