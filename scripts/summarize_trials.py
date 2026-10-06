#!/usr/bin/env python3
"""CLI to score a TrialOutcomeLogger CSV against a success-rate threshold.

Not a ROS entry point — run by hand after a batch of manual doorway trials,
e.g.:
    python3 scripts/summarize_trials.py results/room2_trials.csv --room 2
"""

import argparse
import sys

from arams_mission.trial_summary import TrialSummarizer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path', help='Path to the TrialOutcomeLogger CSV.')
    parser.add_argument('--room', type=int, required=True, help='Room id to summarize.')
    parser.add_argument(
        '--threshold', type=float, default=0.9,
        help='Minimum success rate to count as PASS (default: 0.9).')
    args = parser.parse_args()

    summary = TrialSummarizer.from_csv(args.csv_path, args.room, args.threshold)
    verdict = 'PASS' if summary.meets_threshold else 'FAIL'
    print(f'room {args.room}: {summary.succeeded}/{summary.total} succeeded '
          f'({summary.success_rate:.0%}) — {verdict} (threshold {args.threshold:.0%})')
    sys.exit(0 if summary.meets_threshold else 1)


if __name__ == '__main__':
    main()
