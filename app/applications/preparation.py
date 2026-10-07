from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.candidate.cv_tailoring import (
    AI_DATA_ENGINEERING_CV,
    BI_DATA_ANALYTICS_CV,
    DATA_ENGINEERING_CV,
    PROFILES,
    build_tailored_cv,
    select_cv_version,
    write_tailored_cv,
)
from app.candidate.profile import build_candidate_profile
from app.tracking.db import DB_PATH, save_prepared_application


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESUME = ROOT / "data" / "resume"
DEFAULT_OUTPUT = ROOT / "data" / "applications" / "prepared"
CV_OUTPUT = ROOT / "data" / "candidate" / "cvs"


def _cover_letter(job: dict[str, Any], cv: dict[str, Any], version: str) -> str:
    company = str(job.get("company") or "the hiring team")
    title = str(job.get("title") or "the advertised role")
    location = str(job.get("location") or "Italy")
    location_phrase = f" in {location}" if location.strip().upper() != "UNKNOWN" else ""

    if version == AI_DATA_ENGINEERING_CV:
        experience = (
            "In my current AI Engineer work at X VIEW (CESI SpA), I build Python document-ingestion workflows, "
            "integrate a REST API with Oracle APEX, and use Qdrant and Azure OpenAI embeddings for semantic retrieval. "
            "My other current engagement at X VIEW (Poste Italiane) adds hands-on Oracle ODI, SQL/PLSQL, and data-warehouse experience."
        )
        project = (
            "I have also built a Python ETL project that loads heterogeneous data into MySQL, providing additional practical experience "
            "with data preparation and downstream analytics."
        )
    elif version == BI_DATA_ANALYTICS_CV:
        experience = (
            "At X VIEW (Telecom Italia Sparkle), I migrated 150+ enterprise telecom reports from Hyperion to Oracle BI (OBIEE), "
            "designed reporting models across Physical, BMM, and Presentation layers, and improved ETL workflows. "
            "My current Poste Italiane engagement includes Oracle ODI, SQL/PLSQL, and DWH reconciliation and validation."
        )
        project = (
            "My Airbnb Amsterdam project also includes data preparation, Python ETL into MySQL, and Tableau dashboards."
        )
    else:
        experience = (
            "At X VIEW (Poste Italiane), I design and maintain Oracle Data Integrator ETL/ELT processes, develop Oracle transformations "
            "with SQL and PL/SQL, and validate data-warehouse reconciliation and data quality. Previously, at X VIEW (Telecom Italia Sparkle), "
            "I migrated 150+ enterprise telecom reports from Hyperion to Oracle BI (OBIEE) and optimized data models and ETL workflows."
        )
        project = (
            "My Airbnb Amsterdam project adds Python ETL experience, transforming heterogeneous datasets and loading them into MySQL "
            "for downstream analysis."
        )

    return "\n\n".join(
        [
            f"Dear {company} Recruitment Team,",
            (
                f"I am applying for the {title} role{location_phrase}. The role's focus on data engineering and reliable data workflows "
                "matches my documented experience across enterprise ETL, data warehousing, and analytics."
            ),
            experience,
            project,
            (
                "I would welcome the opportunity to discuss how this combination of enterprise data engineering and analytics experience "
                "could contribute to the team."
            ),
            "Kind regards,\nSmeet Nilvarna",
        ]
    )


def _answer(
    question_id: str,
    question: str,
    answer: str,
    source: str,
    human_review_required: bool = False,
    review_note: str | None = None,
) -> dict[str, Any]:
    result = {
        "question_id": question_id,
        "question": question,
        "answer": answer,
        "source": source,
        "approval_status": "DRAFT",
        "human_review_required": human_review_required,
    }
    if review_note:
        result["review_note"] = review_note
    return result


def _build_answers(job: dict[str, Any], cv: dict[str, Any], version: str) -> list[dict[str, Any]]:
    candidate = build_candidate_profile(cv["source_path"])
    relevant_skills = ", ".join(job.get("match", {}).get("matched_keywords", []))
    motivation = (
        f"I am interested in the {job.get('title', 'role')} because the advertised work aligns with my experience in "
        f"{relevant_skills or 'data engineering and analytics'}. My CV documents enterprise ETL/data-warehouse work and "
        "Python-based data projects; I would like to apply that foundation to the responsibilities described for this role."
    )
    skills_answer = (
        f"My relevant documented skills include {relevant_skills}. My experience includes Oracle ODI ETL/ELT, SQL/PLSQL, "
        "data-warehouse transformations and validation, plus Python ETL project work."
    )
    current_roles = (
        "Data Analyst / BI Consultant at X VIEW (Poste Italiane), January 2026-present; "
        "AI Engineer at X VIEW (CESI SpA), June 2026-present. The CV lists these as concurrent engagements."
    )

    return [
        _answer("current_location", "Where are you currently based?", "Milan, Italy", "Candidate CV/profile"),
        _answer("current_position", "What is your current position?", current_roles, "Candidate CV"),
        _answer(
            "years_experience",
            "How many years of relevant professional experience do you have?",
            f"Approximately {candidate.years_of_experience} years, based on the candidate profile; overlapping roles are not double-counted.",
            "Candidate profile and CV dates",
        ),
        _answer(
            "education",
            "What is your highest completed education?",
            "Master of Science in Engineering in Computer Science, Sapienza University of Rome (2021-2025).",
            "Candidate CV",
        ),
        _answer("english_proficiency", "What is your English proficiency?", "IELTS C1 Proficient.", "IELTS certification listed on CV"),
        _answer(
            "italian_proficiency",
            "What is your Italian proficiency?",
            "UNKNOWN",
            "Not stated in CV",
            True,
            "Confirm your Italian proficiency before answering.",
        ),
        _answer("relevant_skills", "Which skills are most relevant to this role?", skills_answer, "Candidate CV and extracted job posting"),
        _answer("motivation", "Why are you interested in this role?", motivation, "Candidate CV and extracted job posting"),
        _answer(
            "salary_expectation",
            "What are your salary expectations?",
            "UNKNOWN",
            "Not provided",
            True,
            "Requires your direction; no salary commitment has been drafted.",
        ),
        _answer("notice_period", "What is your notice period or availability?", "UNKNOWN", "Not provided", True, "Requires your input."),
        _answer(
            "work_authorization",
            "Are you authorized to work in Italy, and will you require sponsorship?",
            "UNKNOWN",
            "Not provided",
            True,
            "Confirm work authorization and sponsorship needs; no immigration claim has been drafted.",
        ),
        _answer(
            "relocation",
            "Are you willing to relocate or commit to a particular office schedule?",
            "UNKNOWN",
            "Candidate CV location; commitment not provided",
            True,
            "Currently based in Milan, but confirm any relocation or office-frequency commitment.",
        ),
        _answer("selected_cv", "Which CV version is being used?", version, "Role-to-CV selection rule"),
    ]


def prepare_job_application(
    job: dict[str, Any],
    resume_path: str | Path = DEFAULT_RESUME,
    output_dir: str | Path = DEFAULT_OUTPUT,
    db_path: str | Path = DB_PATH,
) -> dict[str, Any]:
    match = job.get("match", {})
    if match.get("tier") not in {"A", "B"}:
        raise ValueError("Application preparation is limited to Tier A/B opportunities.")
    if match.get("hard_rejection_reasons"):
        raise ValueError("Cannot prepare an application for a job with a hard rejection reason.")

    version = job.get("recommended_cv") or select_cv_version(job)
    if version not in PROFILES:
        version = select_cv_version(job)

    cv_path = CV_OUTPUT / f"{version}.docx"
    if not cv_path.exists():
        write_tailored_cv(resume_path, version, cv_path)
    cv = build_tailored_cv(resume_path, version)
    cover_letter = _cover_letter(job, cv, version)
    answers = _build_answers(job, cv, version)
    concerns = list(match.get("missing_requirements", []))
    if any(item["question_id"] == "italian_proficiency" for item in answers):
        concerns.append("Italian proficiency is not stated in the CV; verify any language requirement.")

    job_id = str(job.get("job_id") or "")
    if not job_id:
        raise ValueError("Cannot prepare an application without a stable job_id.")
    prepared_at = date.today().isoformat()
    package = {
        "job_id": job_id,
        "company": job.get("company", "UNKNOWN"),
        "title": job.get("title", "UNKNOWN"),
        "location": job.get("location", "UNKNOWN"),
        "match_score": match.get("total_score", "UNKNOWN"),
        "tier": match.get("tier", "UNKNOWN"),
        "selected_cv": version,
        "selected_cv_path": str(cv_path),
        "cover_letter": cover_letter,
        "answers": answers,
        "potential_concerns": concerns,
        "application_url": job.get("application_url", "UNKNOWN"),
        "application_form_url": job.get("application_form_url", "UNKNOWN"),
        "status": "READY_TO_APPLY",
        "prepared_at": prepared_at,
        "cover_letter_approval_status": "DRAFT",
        "submission_performed": False,
    }

    output_path = Path(output_dir) / job_id
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "cover_letter.md").write_text(cover_letter + "\n", encoding="utf-8")
    (output_path / "answers.json").write_text(json.dumps(answers, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_path / "preparation.json").write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")

    save_prepared_application(
        job_id=job_id,
        cv_version=version,
        cover_letter=cover_letter,
        answers=answers,
        notes={
            "selected_cv_path": str(cv_path),
            "potential_concerns": concerns,
            "submission_performed": False,
        },
        db_path=db_path,
    )
    return package


def prepare_ranked_jobs(
    report: dict[str, Any],
    resume_path: str | Path = DEFAULT_RESUME,
    output_dir: str | Path = DEFAULT_OUTPUT,
    db_path: str | Path = DB_PATH,
) -> list[dict[str, Any]]:
    packages = []
    for job in report.get("ranked_jobs", []):
        if job.get("match", {}).get("tier") not in {"A", "B"}:
            continue
        if job.get("match", {}).get("hard_rejection_reasons"):
            continue
        packages.append(
            prepare_job_application(
                job,
                resume_path=resume_path,
                output_dir=output_dir,
                db_path=db_path,
            )
        )
    return packages
