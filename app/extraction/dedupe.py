from __future__ import annotations

from collections.abc import Iterable


def _url_quality(url: str) -> int:
    value = (url or "").lower()
    if "company" in value or "jobs" in value and ".com" in value:
        return 2
    if "linkedin" in value:
        return 1
    if "indeed" in value or "glassdoor" in value:
        return 0
    return 1


def _normalized_key(job: dict) -> tuple[str, str, str]:
    company = (job.get("company") or "").strip().lower()
    title = (job.get("title") or "").strip().lower()
    location = (job.get("location") or "").strip().lower()
    return (company, title, location)


def deduplicate_jobs(jobs: Iterable[dict]) -> list[dict]:
    selected: dict[tuple[str, str, str], dict] = {}

    for job in jobs:
        key = _normalized_key(job)
        if key not in selected:
            selected[key] = job
            continue

        current = selected[key]
        current_quality = _url_quality(str(current.get("application_url") or ""))
        candidate_quality = _url_quality(str(job.get("application_url") or ""))

        if candidate_quality > current_quality:
            selected[key] = job

    return list(selected.values())
