from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.candidate.profile import CandidateProfile
from app.extraction.models import JobRecord
from app.matching.scorer import score_job_match


LISTING_TERMS = (
    "jobs in",
    "job search",
    "salary",
    "salaries",
    "open positions",
    "top ",
    "best ",
    "careers -",
)


def is_scoreable_job(job: dict) -> bool:
    title = str(job.get("title") or "").strip().lower()
    url = str(job.get("application_url") or "").strip().lower()
    parsed = urlparse(url)
    path = parsed.path.lower()

    if not title or title == "unknown" or not url or url == "unknown":
        return False
    if any(term in title for term in LISTING_TERMS):
        return False
    if "/in/" in path and "linkedin.com" in parsed.netloc:
        return False
    if any(term in path for term in ("/salaries/", "/search/", "/jobs-in-", "/job-search/")):
        return False
    if "linkedin.com" in parsed.netloc and "/jobs/" in path and "-jobs" in path:
        return False
    if not re.search(r"\b(engineer|developer|analyst|consultant|scientist|architect)\b", title):
        return False
    return True


def exclusion_reason(job: dict) -> str:
    title = str(job.get("title") or "").strip().lower()
    url = str(job.get("application_url") or "").strip().lower()
    parsed = urlparse(url)
    path = parsed.path.lower()
    if not title or title == "unknown" or not url or url == "unknown":
        return "Missing job title or application URL."
    if any(term in title for term in LISTING_TERMS):
        return "Search, category, salary, or aggregator page rather than one vacancy."
    if "/in/" in path and "linkedin.com" in parsed.netloc:
        return "Professional profile rather than a job posting."
    if any(term in path for term in ("/salaries/", "/search/", "/jobs-in-", "/job-search/")):
        return "Search or salary page rather than one vacancy."
    if "linkedin.com" in parsed.netloc and "/jobs/" in path and "-jobs" in path:
        return "LinkedIn job-search results page rather than one vacancy."
    if not re.search(r"\b(engineer|developer|analyst|consultant|scientist|architect)\b", title):
        return "Title does not identify a target technical role."
    return "Not an individual vacancy."


def _infer_company(job: dict) -> str:
    company = str(job.get("company") or "UNKNOWN").strip()
    if company and company.lower() != "unknown":
        return company

    host = urlparse(str(job.get("application_url") or "")).netloc.lower()
    known_hosts = {
        "careers.allianz.com": "Allianz",
        "www.accenture.com": "Accenture",
        "careers.nttdata.com": "NTT DATA",
        "careers.bcg.com": "BCG X",
    }
    for domain, name in known_hosts.items():
        if host.endswith(domain):
            return name
    return "UNKNOWN"


def _to_job_record(job: dict) -> JobRecord:
    required = {
        "job_id": job.get("job_id", "UNKNOWN"),
        "title": job.get("title", "UNKNOWN"),
        "company": _infer_company(job),
        "location": job.get("location", "UNKNOWN"),
        "country": job.get("country", "UNKNOWN"),
        "remote_status": job.get("remote_status", "UNKNOWN"),
        "employment_type": job.get("employment_type", "UNKNOWN"),
    }
    optional = {
        key: job[key]
        for key in JobRecord.__dataclass_fields__
        if key in job and key not in required
    }
    return JobRecord(**required, **optional)


def _canonical_url(value: str) -> str:
    parsed = urlparse(str(value or ""))
    if not parsed.scheme or not parsed.netloc:
        return ""
    ignored = {"ref", "source", "trk", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}
    query = urlencode([(key, val) for key, val in parse_qsl(parsed.query) if key.lower() not in ignored])
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/").lower(), "", query, ""))


def find_previous_application(job: dict, previous_applications: list[dict]) -> dict | None:
    url = _canonical_url(job.get("application_url", ""))
    company = _norm_identity(job.get("company"))
    title = _title_identity(job.get("title"), job.get("company"))
    location = _norm_identity(job.get("location"))
    for application in previous_applications:
        previous_url = _canonical_url(application.get("application_url", ""))
        if url and previous_url and url == previous_url:
            return application
        previous_company = _norm_identity(application.get("company"))
        previous_title = _title_identity(application.get("title"), application.get("company"))
        previous_location = _norm_identity(application.get("location"))
        if (
            company != "unknown"
            and title != "unknown"
            and location != "unknown"
            and (company, title, location) == (previous_company, previous_title, previous_location)
        ):
            return application
    return None


def _norm_identity(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip().replace("milano", "milan")


def _title_identity(title: object, company: object) -> str:
    """Treat a title suffixed with its employer name as the same role title."""
    normalized_title = _norm_identity(title)
    normalized_company = _norm_identity(company)
    suffix = f" {normalized_company}"
    if normalized_company and normalized_title.endswith(suffix):
        return normalized_title[: -len(suffix)].strip()
    return normalized_title


def rank_jobs(
    jobs: list[dict],
    candidate: CandidateProfile,
    previous_applications: list[dict] | None = None,
) -> list[dict]:
    ranked = []
    for job in jobs:
        if not is_scoreable_job(job):
            continue
        if find_previous_application(job, previous_applications or []):
            continue
        record = _to_job_record(job)
        match = score_job_match(record, candidate)
        completeness_fields = [
            "company",
            "location",
            "experience_required",
            "technologies",
            "responsibilities",
            "mandatory_requirements",
            "full_job_description",
        ]
        populated = sum(
            bool(job.get(field)) and str(job.get(field)).strip().lower() != "unknown"
            for field in completeness_fields
        )
        match["data_confidence"] = round(populated / len(completeness_fields), 2)
        match["review_required"] = (
            match["data_confidence"] < 0.6
            or record.company == "UNKNOWN"
            or record.location == "UNKNOWN"
        )
        ranked.append({**job, "company": record.company, "match": match})

    return sorted(ranked, key=lambda item: item["match"]["total_score"], reverse=True)
