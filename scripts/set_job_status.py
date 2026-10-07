from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tracking.db import JOB_STATUSES, set_job_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Set a durable workflow status for a tracked job.")
    parser.add_argument("job_id", help="Job ID shown in the ranking report or database")
    parser.add_argument("status", choices=sorted(JOB_STATUSES), type=str.upper)
    parser.add_argument("--note", help="Optional reason, such as 'Applied in July 2026'.")
    parser.add_argument("--reason", help="Why this status was chosen; shown in the job history.")
    arguments = parser.parse_args()
    set_job_status(arguments.job_id, arguments.status, notes=arguments.note, reason=arguments.reason)
    print(f"Updated {arguments.job_id} to {arguments.status}.")


if __name__ == "__main__":
    main()
