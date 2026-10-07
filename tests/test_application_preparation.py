import json

from app.applications.preparation import prepare_job_application, prepare_ranked_jobs
from app.tracking.db import get_jobs, init_db, upsert_jobs


def _job(**overrides):
    job = {
        "job_id": "acc-001",
        "title": "Junior Data Engineer",
        "company": "Accenture",
        "location": "Milan, Italy",
        "application_url": "https://example.com/jobs/acc-001",
        "full_job_description": "Build data models, data pipelines, and data quality processes.",
        "recommended_cv": "DATA_ENGINEERING_CV",
        "recommended_cv_path": "data/candidate/cvs/DATA_ENGINEERING_CV.docx",
        "match": {
            "tier": "A",
            "total_score": 82.5,
            "matched_keywords": ["Python", "ETL", "Data Warehouse"],
            "missing_requirements": ["AWS", "Spark"],
            "hard_rejection_reasons": [],
            "review_required": True,
        },
    }
    job.update(overrides)
    return job


def _seed_job(db_path):
    init_db(db_path)
    upsert_jobs([_job()], db_path)


def test_preparation_creates_role_specific_material_and_flags_unknowns(tmp_path):
    db_path = tmp_path / "preparation.sqlite"
    _seed_job(db_path)
    result = prepare_job_application(
        _job(),
        resume_path="data/resume/Smeet_s_Resume (1).pdf",
        output_dir=tmp_path / "prepared",
        db_path=db_path,
    )

    letter = result["cover_letter"]
    assert "Accenture" in letter
    assert "Junior Data Engineer" in letter
    assert "Oracle Data Integrator" in letter
    assert "150+" in letter
    assert "AWS" not in letter
    assert result["selected_cv"] == "DATA_ENGINEERING_CV"
    assert result["status"] == "READY_TO_APPLY"

    answers = {item["question_id"]: item for item in result["answers"]}
    assert answers["english_proficiency"]["answer"] == "IELTS C1 Proficient."
    assert answers["salary_expectation"]["answer"] == "UNKNOWN"
    assert answers["salary_expectation"]["human_review_required"] is True
    assert answers["work_authorization"]["human_review_required"] is True
    assert result["submission_performed"] is False


def test_ranked_job_preparation_only_includes_tier_a_and_b(tmp_path):
    db_path = tmp_path / "ranked.sqlite"
    _seed_job(db_path)
    report = {
        "ranked_jobs": [
            _job(),
            _job(job_id="low-001", title="Data Engineer", match={"tier": "D"}),
        ]
    }

    prepared = prepare_ranked_jobs(
        report,
        resume_path="data/resume/Smeet_s_Resume (1).pdf",
        output_dir=tmp_path / "prepared",
        db_path=db_path,
    )

    assert len(prepared) == 1
    assert prepared[0]["job_id"] == "acc-001"
    assert (tmp_path / "prepared" / "acc-001" / "cover_letter.md").exists()
    assert (tmp_path / "prepared" / "acc-001" / "answers.json").exists()


def test_preparation_persists_ready_to_apply_without_submission(tmp_path):
    db_path = tmp_path / "applications.sqlite"
    _seed_job(db_path)

    prepare_job_application(
        _job(),
        resume_path="data/resume/Smeet_s_Resume (1).pdf",
        output_dir=tmp_path / "prepared",
        db_path=db_path,
    )

    with __import__("sqlite3").connect(db_path) as conn:
        row = conn.execute("SELECT status, cv_version, cover_letter, answers FROM applications").fetchone()
    stored_jobs = get_jobs(db_path=db_path)

    assert row[0] == "READY_TO_APPLY"
    assert row[1] == "DATA_ENGINEERING_CV"
    assert json.loads(row[3])[0]["approval_status"] == "DRAFT"
    assert stored_jobs[0]["status"] == "READY_TO_APPLY"


def test_repreparing_pending_application_updates_in_place(tmp_path):
    db_path = tmp_path / "repeat.sqlite"
    _seed_job(db_path)
    arguments = {
        "resume_path": "data/resume/Smeet_s_Resume (1).pdf",
        "output_dir": tmp_path / "prepared",
        "db_path": db_path,
    }

    prepare_job_application(_job(), **arguments)
    prepare_job_application(_job(), **arguments)

    with __import__("sqlite3").connect(db_path) as conn:
        application_count = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

    assert application_count == 1


def test_preparation_refuses_to_overwrite_submitted_application(tmp_path):
    import sqlite3

    from app.tracking.db import save_prepared_application

    db_path = tmp_path / "submitted.sqlite"
    _seed_job(db_path)
    save_prepared_application("acc-001", "DATA_ENGINEERING_CV", "Draft", [], {}, db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE applications SET status = 'SUBMITTED' WHERE job_id = 'acc-001'")

    import pytest

    with pytest.raises(ValueError, match="already progressed to SUBMITTED"):
        prepare_job_application(
            _job(),
            resume_path="data/resume/Smeet_s_Resume (1).pdf",
            output_dir=tmp_path / "prepared",
            db_path=db_path,
        )
