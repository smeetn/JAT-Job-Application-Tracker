from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.candidate.profile import build_candidate_profile
from app.discovery.search import discover_jobs
from app.extraction.models import JobRecord
from app.matching.scorer import score_job_match


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    profile = build_candidate_profile("data/resume")
    jobs = discover_jobs(profile)

    scored_jobs = []
    for item in jobs:
        job = JobRecord(**item)
        score = score_job_match(job, profile)
        job.score = score["total_score"]
        scored_jobs.append({
            "job_id": job.job_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "tier": score["tier"],
            "score": score["total_score"],
            "matched_keywords": score["matched_keywords"],
            "missing_requirements": score["missing_requirements"],
        })

    report_path = root / "data" / "reports" / "initial_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "candidate_name": profile.name,
        "target_market": profile.target_locations,
        "jobs_evaluated": len(scored_jobs),
        "jobs_by_tier": {
            "A": sum(1 for job in scored_jobs if job["tier"] == "A"),
            "B": sum(1 for job in scored_jobs if job["tier"] == "B"),
            "C": sum(1 for job in scored_jobs if job["tier"] == "C"),
            "D": sum(1 for job in scored_jobs if job["tier"] == "D"),
        },
        "top_opportunities": sorted(scored_jobs, key=lambda job: job["score"], reverse=True),
    }, indent=2), encoding="utf-8")

    print("MILAN JOB AGENT — INITIAL REPORT")
    print(f"Jobs discovered: {len(scored_jobs)}")
    for entry in sorted(scored_jobs, key=lambda job: job["score"], reverse=True):
        print(f"- {entry['title']} @ {entry['company']} | Tier {entry['tier']} | Score {entry['score']} | Keywords {', '.join(entry['matched_keywords']) or 'N/A'}")


if __name__ == "__main__":
    main()
