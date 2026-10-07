from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.candidate.profile import build_candidate_profile
from app.discovery.search import discover_jobs
from app.extraction.dedupe import deduplicate_jobs
from app.tracking.db import upsert_jobs


def main() -> None:
    profile = build_candidate_profile("data/resume")
    raw_jobs = discover_jobs(profile, use_firecrawl=True)
    unique_jobs = deduplicate_jobs(raw_jobs)
    database_counts = upsert_jobs(unique_jobs)

    output_path = Path(__file__).resolve().parents[1] / "data" / "jobs" / "real_discovered_jobs.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(unique_jobs[:25], indent=2), encoding="utf-8")

    print(f"Raw results: {len(raw_jobs)}")
    print(f"Unique jobs: {len(unique_jobs)}")
    print(f"SQLite: {database_counts['inserted']} inserted, {database_counts['updated']} updated")
    for job in unique_jobs[:10]:
        print(f"- {job.get('title')} @ {job.get('company')} | {job.get('location')} | {job.get('application_url')}")


if __name__ == "__main__":
    main()
