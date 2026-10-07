import sqlite3

from app.tracking.db import get_jobs, get_suppressed_jobs, init_db, save_analysis_results, set_job_status, upsert_jobs


def _job(**overrides):
    record = {
        "job_id": "initial-id",
        "title": "Data Engineer",
        "company": "Acme Data",
        "location": "Milan, Italy",
        "country": "Italy",
        "remote_status": "Hybrid",
        "employment_type": "Full-time",
        "salary": "UNKNOWN",
        "salary_currency": "UNKNOWN",
        "experience_required": "2+ years",
        "education_required": "UNKNOWN",
        "technologies": ["Python", "SQL"],
        "responsibilities": ["Build data pipelines"],
        "mandatory_requirements": ["Python", "SQL"],
        "preferred_requirements": [],
        "language_requirements": [],
        "visa_work_authorization_requirements": "UNKNOWN",
        "application_url": "https://acme.com/careers/data-engineer",
        "source": "company_site",
        "original_posting_date": "UNKNOWN",
        "discovered_date": "2026-10-02",
        "closing_date": "UNKNOWN",
        "company_career_url": "https://acme.com/careers",
        "full_job_description": "Build pipelines in Python and SQL.",
        "application_platform": "UNKNOWN",
        "score": None,
    }
    record.update(overrides)
    return record


def test_repeated_discovery_updates_existing_record_and_preserves_status(tmp_path):
    db_path = tmp_path / "tracking.sqlite"
    init_db(db_path)

    first = upsert_jobs([_job()], db_path)
    set_job_status("initial-id", "REVIEWING", score=84.5, db_path=db_path)
    second = upsert_jobs(
        [
            _job(
                job_id="changed-result-id",
                application_url="https://acme.com/careers/data-engineer?utm_source=linkedin",
                full_job_description="Updated description: build Python SQL ETL pipelines.",
            )
        ],
        db_path,
    )

    jobs = get_jobs(db_path=db_path)

    assert first == {"inserted": 1, "updated": 0}
    assert second == {"inserted": 0, "updated": 1}
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == "initial-id"
    assert jobs[0]["status"] == "REVIEWING"
    assert jobs[0]["score"] == 84.5
    assert "Updated description" in jobs[0]["full_job_description"]


def test_init_db_migrates_existing_jobs_table(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                country TEXT,
                remote_status TEXT,
                employment_type TEXT,
                salary TEXT,
                salary_currency TEXT,
                experience_required TEXT,
                education_required TEXT,
                technologies TEXT,
                responsibilities TEXT,
                mandatory_requirements TEXT,
                preferred_requirements TEXT,
                language_requirements TEXT,
                visa_work_authorization_requirements TEXT,
                application_url TEXT,
                source TEXT,
                original_posting_date TEXT,
                discovered_date TEXT,
                closing_date TEXT,
                company_career_url TEXT,
                full_job_description TEXT,
                application_platform TEXT,
                score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO jobs (job_id, title, company, location)
            VALUES ('legacy-1', 'Data Engineer', 'Acme', 'Milan, Italy');
            """
        )

    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    jobs = get_jobs(db_path=db_path)

    assert {"dedupe_key", "status", "notes", "updated_at"}.issubset(columns)
    assert jobs[0]["job_id"] == "legacy-1"
    assert jobs[0]["status"] == "NEW"


def test_analysis_result_persists_score_status_and_review_notes(tmp_path):
    db_path = tmp_path / "analysis.sqlite"
    init_db(db_path)

    counts = save_analysis_results(
        [
            {
                **_job(),
                "recommended_cv": "DATA_ENGINEERING_CV",
                "match": {
                    "total_score": 82.5,
                    "tier": "A",
                    "review_required": True,
                    "hard_rejection_reasons": [],
                },
            }
        ],
        db_path,
    )
    stored = get_jobs(db_path=db_path, status="REVIEWING")

    assert counts == {"inserted": 1, "updated": 0}
    assert stored[0]["score"] == 82.5
    assert stored[0]["status"] == "REVIEWING"
    assert '"tier": "A"' in stored[0]["notes"]
    assert '"recommended_cv": "DATA_ENGINEERING_CV"' in stored[0]["notes"]


def test_manual_already_applied_status_is_preserved_and_suppressed(tmp_path):
    db_path = tmp_path / "manual-status.sqlite"
    upsert_jobs([_job()], db_path)
    set_job_status("initial-id", "ALREADY_APPLIED", notes="Applied before using this tracker.", db_path=db_path)
    upsert_jobs([_job(job_id="new-result-id")], db_path)

    stored = get_jobs(db_path)[0]
    suppressed = get_suppressed_jobs(db_path)

    assert stored["status"] == "ALREADY_APPLIED"
    assert stored["notes"] == "Applied before using this tracker."
    assert [job["job_id"] for job in suppressed] == ["initial-id"]


def test_distinct_jobs_with_colliding_source_ids_get_distinct_database_ids(tmp_path):
    db_path = tmp_path / "collisions.sqlite"
    counts = upsert_jobs(
        [
            _job(job_id="same-source-id", company="Acme"),
            _job(
                job_id="same-source-id",
                company="Other Company",
                application_url="https://other.example/jobs/data-engineer",
            ),
        ],
        db_path,
    )
    stored = get_jobs(db_path=db_path)

    assert counts == {"inserted": 2, "updated": 0}
    assert len(stored) == 2
    assert len({job["job_id"] for job in stored}) == 2


def test_same_application_url_with_cleaned_title_updates_existing_job(tmp_path):
    db_path = tmp_path / "title-update.sqlite"
    init_db(db_path)
    first = upsert_jobs([_job(job_id="search-id", title="Data Engineer job listing")], db_path)
    second = upsert_jobs(
        [_job(job_id="clean-id", title="Data Engineer", application_url="https://acme.com/careers/data-engineer?utm_source=linkedin")],
        db_path,
    )
    stored = get_jobs(db_path=db_path)

    assert first == {"inserted": 1, "updated": 0}
    assert second == {"inserted": 0, "updated": 1}
    assert len(stored) == 1
    assert stored[0]["job_id"] == "search-id"
    assert stored[0]["title"] == "Data Engineer"


def test_migration_merges_duplicate_urls_and_keeps_application_link(tmp_path):
    db_path = tmp_path / "duplicate-urls.sqlite"
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, dedupe_key, title, company, location, application_url, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("old-job", "old-dedupe", "Long search title", "Acme", "Milan, Italy", "https://acme.com/job/1", "READY_TO_APPLY"),
        )
        conn.execute(
            "INSERT INTO jobs (job_id, dedupe_key, title, company, location, application_url, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("new-job", "new-dedupe", "Data Engineer", "Acme", "UNKNOWN", "https://acme.com/job/1?utm_source=linkedin", "REVIEWING"),
        )
        conn.execute(
            "INSERT INTO applications (job_id, cv_version, status) VALUES (?, ?, ?)",
            ("old-job", "DATA_ENGINEERING_CV", "READY_TO_APPLY"),
        )

    init_db(db_path)
    stored = get_jobs(db_path=db_path)
    with sqlite3.connect(db_path) as conn:
        application = conn.execute("SELECT job_id, status FROM applications").fetchone()

    assert len(stored) == 1
    assert stored[0]["job_id"] == "old-job"
    assert stored[0]["title"] == "Data Engineer"
    assert application == ("old-job", "READY_TO_APPLY")
