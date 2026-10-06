"""Summarizes logged navigation trial outcomes into a pass/fail success rate."""

import csv
from dataclasses import dataclass

from arams_mission.room_navigator import NavigationOutcome


@dataclass
class TrialSummary:
    """Outcome tally for a batch of navigation trials."""

    total: int
    succeeded: int
    success_rate: float
    meets_threshold: bool


class TrialSummarizer:
    """Tallies (room_id, outcome_name) rows into a TrialSummary."""

    def __init__(self, success_threshold: float = 0.9) -> None:
        self._success_threshold = success_threshold

    def summarize(self, rows: list[tuple[int, str]]) -> TrialSummary:
        """Summarize outcome rows for a single room.

        Args:
            rows: (room_id, outcome_name) pairs, already filtered to one room.

        Returns:
            The tally and whether it meets the configured success threshold.
        """
        total = len(rows)
        succeeded = sum(1 for _, outcome in rows if outcome == NavigationOutcome.SUCCEEDED.name)
        success_rate = succeeded / total if total else 0.0
        return TrialSummary(
            total=total,
            succeeded=succeeded,
            success_rate=success_rate,
            meets_threshold=success_rate >= self._success_threshold,
        )

    @classmethod
    def from_csv(
        cls, csv_path: str, room_id: int, success_threshold: float = 0.9,
    ) -> TrialSummary:
        """Read a TrialOutcomeLogger CSV and summarize one room's rows."""
        with open(csv_path, newline='') as csv_file:
            rows = [
                (int(row['room_id']), row['outcome'])
                for row in csv.DictReader(csv_file)
                if int(row['room_id']) == room_id
            ]
        return cls(success_threshold).summarize(rows)
