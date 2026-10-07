from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tracking.availability import assess_availability
from app.tracking.db import SUPPRESSED_JOB_STATUSES, get_jobs, update_job_availability


def main() -> None:
    active_jobs = [job for job in get_jobs() if job["status"] not in SUPPRESSED_JOB_STATUSES]
    summary = {"OPEN": 0, "CLOSED": 0, "UNKNOWN": 0, "UNREACHABLE": 0}
    for job in active_jobs:
        result = assess_availability(str(job.get("application_url") or ""))
        update_job_availability(job["job_id"], result.status)
        summary[result.status] += 1
        print(f"{result.status:11} | {job['title']} @ {job['company']} | {result.reason}")
    print(f"Checked {len(active_jobs)} active jobs: {summary}")


if __name__ == "__main__":
    main()
