import sqlite3

from app.candidate.profile import build_candidate_profile
from app.matching.ranker import find_previous_application, rank_jobs
from app.tracking.db import get_jobs, init_db, record_historical_application, set_application_status, upsert_jobs


def _job(job_id, url, company="Acme", title="Data Engineer", location="Milan, Italy"):
    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "country": "Italy",
        "remote_status": "Hybrid",
        "employment_type": "Full-time",
        "experience_required": "2 years",
        "education_required": "UNKNOWN",
        "technologies": ["Python", "SQL", "ETL", "Oracle", "Data Warehouse"],
        "responsibilities": ["Build ETL pipelines", "Validate data quality"],
        "mandatory_requirements": ["Python", "SQL", "ETL"],
        "preferred_requirements": [],
        "full_job_description": "Build Python SQL ETL pipelines in a data warehouse.",
        "application_url": url,
        "source": "company_site",
    }


def test_previous_application_matches_tracking_url_and_identity():
    prior = _job("old-id", "https://acme.example/jobs/data-engineer")
    current = _job("new-search-id", "https://acme.example/jobs/data-engineer?utm_source=linkedin")

    assert find_previous_application(current, [prior]) is prior


def test_previous_application_matches_employer_suffix_in_search_title():
    prior = _job("old-id", "UNKNOWN", company="Accenture", title="Junior Data Engineer")
    current = _job(
        "search-id",
        "https://careers.accenture.com/jobs/junior-data-engineer",
        company="Accenture",
        title="Junior Data Engineer - Accenture",
    )

    assert find_previous_application(current, [prior]) is prior


def test_ranker_skips_previous_application_but_keeps_distinct_requisition():
    profile = build_candidate_profile()
    applied = _job("old-id", "https://acme.example/jobs/data-engineer")
    repeat = _job("new-search-id", "https://acme.example/jobs/data-engineer?source=linkedin")
    distinct = _job("other-id", "https://acme.example/jobs/data-engineer-2", title="Data Engineer II")

    ranked = rank_jobs([repeat, distinct], profile, previous_applications=[applied])

    assert [job["job_id"] for job in ranked] == ["other-id"]


def test_submitted_status_is_durable_and_date_can_remain_unknown(tmp_path):
    db_path = tmp_path / "applications.sqlite"
    init_db(db_path)
    upsert_jobs([_job("acc-1", "https://acme.example/jobs/data-engineer")], db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO applications (job_id, cv_version, status) VALUES (?, ?, ?)",
            ("acc-1", "DATA_ENGINEERING_CV", "READY_TO_APPLY"),
        )

    set_application_status("acc-1", "SUBMITTED", db_path=db_path)

    with sqlite3.connect(db_path) as conn:
        application = conn.execute(
            "SELECT status, date_submitted FROM applications WHERE job_id = 'acc-1'"
        ).fetchone()
    job = get_jobs(db_path=db_path)[0]

    assert application == ("SUBMITTED", None)
    assert job["status"] == "SUBMITTED"


def test_historical_application_keeps_approximate_date_and_reason(tmp_path):
    db_path = tmp_path / "history.sqlite"
    upsert_jobs([_job("acc-1", "https://acme.example/jobs/data-engineer")], db_path)

    record_historical_application(
        "acc-1",
        "2026-06",
        "MONTH",
        "Applied before using this tracker; do not recommend again.",
        db_path,
    )

    with sqlite3.connect(db_path) as conn:
        application = conn.execute(
            "SELECT date_submitted, submitted_date_precision, status, status_reason FROM applications"
        ).fetchone()
    job = get_jobs(db_path=db_path)[0]

    assert application == ("2026-06", "MONTH", "SUBMITTED", "Applied before using this tracker; do not recommend again.")
    assert job["status"] == "ALREADY_APPLIED"
    assert job["status_reason"] == "Applied before using this tracker; do not recommend again."
