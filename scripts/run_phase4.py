from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.candidate.profile import build_candidate_profile
from app.candidate.cv_tailoring import select_cv_version
from app.extraction.enricher import enrich_job_records
from app.matching.ranker import exclusion_reason, find_previous_application, is_scoreable_job, rank_jobs
from app.tracking.db import get_suppressed_jobs, save_analysis_results


def main() -> None:
    jobs_path = ROOT / "data" / "jobs" / "real_discovered_jobs.json"
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    candidate = build_candidate_profile(ROOT / "data" / "resume")
    scoreable = [job for job in jobs if is_scoreable_job(job)]
    suppressed_jobs = get_suppressed_jobs()
    enriched_scoreable = enrich_job_records(scoreable)
    by_id = {job.get("job_id"): job for job in enriched_scoreable}
    jobs = [by_id.get(job.get("job_id"), job) for job in jobs]
    jobs_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    ranked_jobs = rank_jobs(enriched_scoreable, candidate, suppressed_jobs)
    suppressed_results = [
        {
            "title": job.get("title", "UNKNOWN"),
            "company": job.get("company", "UNKNOWN"),
            "url": job.get("application_url", "UNKNOWN"),
            "status": previous["application_status"],
            "reason": "Previously applied, declined, or closed; suppressed from the active shortlist.",
        }
        for job in enriched_scoreable
        if (previous := find_previous_application(job, suppressed_jobs)) is not None
    ]
    excluded = [
        {
            "title": job.get("title", "UNKNOWN"),
            "url": job.get("application_url", "UNKNOWN"),
            "reason": exclusion_reason(job),
        }
        for job in jobs
        if not is_scoreable_job(job)
    ]

    for job in ranked_jobs:
        job["recommended_cv"] = select_cv_version(job)
        job["recommended_cv_path"] = f"data/candidate/cvs/{job['recommended_cv']}.docx"

    database_counts = save_analysis_results(ranked_jobs)

    report = {
        "report_date": date.today().isoformat(),
        "candidate": candidate.name,
        "candidate_resume": candidate.notes.get("resume_path", "UNKNOWN"),
        "jobs_received": len(jobs),
        "individual_vacancies_scored": len(enriched_scoreable),
        "suppressed_results_excluded": len(suppressed_results),
        "non_vacancy_results_excluded": len(excluded),
        "tier_counts": {
            tier: sum(item["match"]["tier"] == tier for item in ranked_jobs)
            for tier in ("A", "B", "C", "D")
        },
        "database_updates": database_counts,
        "ranked_jobs": ranked_jobs,
        "suppressed_results": suppressed_results,
        "excluded_results": excluded,
        "scoring_note": "Heuristic prioritization only. Unknown job facts are not treated as confirmed; low-confidence records require review.",
    }
    report_path = ROOT / "data" / "reports" / "phase4_ranked_jobs.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("MILAN JOB AGENT — PHASE 4 RANKING")
    print(f"Search results: {len(jobs)} | Individual vacancies scored: {len(scoreable)} | Non-vacancy results excluded: {len(excluded)}")
    print(f"Suppressed from active shortlist: {len(suppressed_results)}")
    print(f"SQLite: {database_counts['inserted']} inserted, {database_counts['updated']} updated")
    print(f"Tier counts: {report['tier_counts']}")
    for item in ranked_jobs:
        match = item["match"]
        print(f"- Tier {match['tier']} | {match['total_score']:.1f} | {item['title']} @ {item['company']} | {item['location']} | review={match['review_required']}")
        print(f"  Matches: {', '.join(match['matched_keywords']) or 'Not enough skill evidence'}")
        print(f"  Gaps: {', '.join(match['missing_requirements']) or 'No extracted gaps'}")
        print(f"  Breakdown: {match['score_breakdown']}")
        print(f"  Enrichment: {item.get('enrichment_status', 'UNKNOWN')} | confidence={match['data_confidence']:.2f}")
        print(f"  URL: {item['application_url']}")
    print(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()
