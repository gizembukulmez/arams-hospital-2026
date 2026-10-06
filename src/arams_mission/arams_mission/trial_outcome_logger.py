"""Appends navigation trial outcomes to a CSV file for repeatability testing."""

import csv
import os
from datetime import datetime, timezone

from arams_mission.room_navigator import NavigationOutcome

_FIELDNAMES = ['timestamp', 'room_id', 'outcome', 'detail']


class TrialOutcomeLogger:
    """Appends one CSV row per navigation trial outcome."""

    def __init__(self, csv_path: str) -> None:
        self._csv_path = csv_path
        if not os.path.exists(csv_path):
            with open(csv_path, 'w', newline='') as csv_file:
                csv.DictWriter(csv_file, fieldnames=_FIELDNAMES).writeheader()

    def log(self, room_id: int, outcome: NavigationOutcome, detail: str) -> None:
        """Append one trial outcome row, timestamped at call time (UTC)."""
        with open(self._csv_path, 'a', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=_FIELDNAMES)
            writer.writerow({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'room_id': room_id,
                'outcome': outcome.name,
                'detail': detail,
            })
