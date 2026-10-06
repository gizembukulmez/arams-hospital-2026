import csv

import pytest

from arams_mission.trial_summary import TrialSummarizer, TrialSummary


def test_all_succeeded_meets_threshold():
    summarizer = TrialSummarizer(success_threshold=0.9)
    rows = [(2, 'SUCCEEDED')] * 10

    summary = summarizer.summarize(rows)

    assert summary == TrialSummary(total=10, succeeded=10, success_rate=1.0, meets_threshold=True)


def test_all_failed_does_not_meet_threshold():
    summarizer = TrialSummarizer(success_threshold=0.9)
    rows = [(2, 'ABORTED')] * 10

    summary = summarizer.summarize(rows)

    assert summary == TrialSummary(total=10, succeeded=0, success_rate=0.0, meets_threshold=False)


def test_mixed_outcomes_above_threshold():
    summarizer = TrialSummarizer(success_threshold=0.9)
    rows = [(2, 'SUCCEEDED')] * 9 + [(2, 'ABORTED')]

    summary = summarizer.summarize(rows)

    assert summary.success_rate == pytest.approx(0.9)
    assert summary.meets_threshold is True


def test_mixed_outcomes_below_threshold():
    summarizer = TrialSummarizer(success_threshold=0.9)
    rows = [(2, 'SUCCEEDED')] * 8 + [(2, 'ABORTED')] * 2

    summary = summarizer.summarize(rows)

    assert summary.success_rate == pytest.approx(0.8)
    assert summary.meets_threshold is False


def test_non_succeeded_outcomes_all_count_as_failures():
    summarizer = TrialSummarizer(success_threshold=0.9)
    rows = [(2, 'ABORTED'), (2, 'CANCELED'), (2, 'REJECTED'), (2, 'UNKNOWN_ROOM')]

    summary = summarizer.summarize(rows)

    assert summary.succeeded == 0


def test_empty_input():
    summarizer = TrialSummarizer(success_threshold=0.9)

    summary = summarizer.summarize([])

    assert summary == TrialSummary(total=0, succeeded=0, success_rate=0.0, meets_threshold=False)


def test_from_csv_filters_to_the_requested_room(tmp_path):
    csv_path = tmp_path / 'trials.csv'
    with open(csv_path, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=['timestamp', 'room_id', 'outcome', 'detail'])
        writer.writeheader()
        writer.writerow({'timestamp': 't1', 'room_id': 1, 'outcome': 'ABORTED', 'detail': ''})
        writer.writerow({'timestamp': 't2', 'room_id': 2, 'outcome': 'SUCCEEDED', 'detail': ''})
        writer.writerow({'timestamp': 't3', 'room_id': 2, 'outcome': 'SUCCEEDED', 'detail': ''})

    summary = TrialSummarizer.from_csv(str(csv_path), room_id=2, success_threshold=0.9)

    assert summary == TrialSummary(total=2, succeeded=2, success_rate=1.0, meets_threshold=True)
