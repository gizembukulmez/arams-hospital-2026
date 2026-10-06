import csv

from arams_mission.room_navigator import NavigationOutcome
from arams_mission.trial_outcome_logger import TrialOutcomeLogger


def read_rows(csv_path):
    with open(csv_path, newline='') as csv_file:
        return list(csv.DictReader(csv_file))


def test_creates_file_with_header(tmp_path):
    csv_path = tmp_path / 'trials.csv'
    TrialOutcomeLogger(str(csv_path))

    rows = read_rows(csv_path)
    assert rows == []
    with open(csv_path) as csv_file:
        header = csv_file.readline().strip()
    assert header == 'timestamp,room_id,outcome,detail'


def test_log_appends_a_row(tmp_path):
    csv_path = tmp_path / 'trials.csv'
    logger = TrialOutcomeLogger(str(csv_path))

    logger.log(2, NavigationOutcome.SUCCEEDED, 'status 4')

    rows = read_rows(csv_path)
    assert len(rows) == 1
    assert rows[0]['room_id'] == '2'
    assert rows[0]['outcome'] == 'SUCCEEDED'
    assert rows[0]['detail'] == 'status 4'


def test_log_multiple_times_appends_without_overwriting(tmp_path):
    csv_path = tmp_path / 'trials.csv'
    logger = TrialOutcomeLogger(str(csv_path))

    logger.log(1, NavigationOutcome.SUCCEEDED, 'status 4')
    logger.log(1, NavigationOutcome.ABORTED, 'status 6')
    logger.log(2, NavigationOutcome.SUCCEEDED, 'status 4')

    rows = read_rows(csv_path)
    assert [(r['room_id'], r['outcome']) for r in rows] == [
        ('1', 'SUCCEEDED'), ('1', 'ABORTED'), ('2', 'SUCCEEDED'),
    ]


def test_reopening_an_existing_file_does_not_rewrite_header(tmp_path):
    csv_path = tmp_path / 'trials.csv'
    TrialOutcomeLogger(str(csv_path)).log(1, NavigationOutcome.SUCCEEDED, 'status 4')

    TrialOutcomeLogger(str(csv_path)).log(1, NavigationOutcome.SUCCEEDED, 'status 4')

    rows = read_rows(csv_path)
    assert len(rows) == 2
