from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.extraction.models import UNKNOWN
from app.tracking.db import record_historical_application, upsert_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a past application so it is never recommended again.")
    parser.add_argument("title", help="Role title used when you applied")
    parser.add_argument("company", help="Employer name")
    parser.add_argument("--location", default="UNKNOWN")
    parser.add_argument("--url", default=UNKNOWN, help="Original job URL if you still have it")
    parser.add_argument("--note", default="Applied before using this tracker.")
    parser.add_argument("--applied-date", help="Exact date (YYYY-MM-DD) or approximate month (YYYY-MM).")
    parser.add_argument("--date-precision", choices=("EXACT", "MONTH", "UNKNOWN"), default="UNKNOWN")
    arguments = parser.parse_args()

    identity = "|".join((arguments.company, arguments.title, arguments.location, arguments.url))
    job_id = f"historical-{hashlib.sha1(identity.encode('utf-8')).hexdigest()[:12]}"
    upsert_jobs([
        {
            "job_id": job_id,
            "title": arguments.title,
            "company": arguments.company,
            "location": arguments.location,
            "country": "Italy" if "ital" in arguments.location.lower() else UNKNOWN,
            "remote_status": UNKNOWN,
            "employment_type": UNKNOWN,
            "application_url": arguments.url,
            "source": "manual_history",
        }
    ])
    application_id = record_historical_application(
        job_id,
        arguments.applied_date,
        arguments.date_precision,
        arguments.note,
    )
    print(f"Recorded {arguments.title} at {arguments.company} as ALREADY_APPLIED ({job_id}; application {application_id}).")


if __name__ == "__main__":
    main()
