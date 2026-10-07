from app.candidate.profile import build_candidate_profile
from app.extraction.models import JobRecord
from app.matching.scorer import score_job_match


def test_candidate_profile_has_milan_target_and_core_skills():
    profile = build_candidate_profile()

    assert profile.name == "Smeet Nilvarna"
    assert "Milan" in profile.target_locations
    assert "Python" in profile.technical_skills
    assert "SQL" in profile.technical_skills
    assert "Oracle" in profile.technical_skills


def test_data_engineer_match_scores_high_for_relevant_role():
    profile = build_candidate_profile()
    job = JobRecord(
        job_id="MIL-001",
        title="Data Engineer",
        company="Acme Data",
        location="Milan, Italy",
        country="Italy",
        remote_status="Hybrid",
        employment_type="Full-time",
        salary="UNKNOWN",
        salary_currency="UNKNOWN",
        experience_required="2+ years",
        education_required="UNKNOWN",
        technologies=["Python", "SQL", "ETL", "Oracle", "Data Warehouse"],
        responsibilities=[
            "Build ETL pipelines",
            "Transform data warehouse models",
            "Validate data quality",
        ],
        mandatory_requirements=["Python", "SQL", "ETL", "Data Warehousing"],
        preferred_requirements=["Airflow"],
        language_requirements=["English"],
        visa_work_authorization_requirements="UNKNOWN",
        application_url="https://example.com/jobs/1",
        source="company_career_page",
        original_posting_date="2026-10-01",
        discovered_date="2026-10-01",
        closing_date="UNKNOWN",
        company_career_url="https://example.com/careers",
        full_job_description="Python, SQL, ETL and Data Warehouse engineering in Milan.",
        application_platform="company_website",
    )

    result = score_job_match(job, profile)

    assert result["tier"] in {"A", "B"}
    assert result["total_score"] >= 70
    assert "Data Warehouse" in result["matched_keywords"]


def test_azure_openai_does_not_claim_general_azure_platform_experience():
    profile = build_candidate_profile()
    job = JobRecord(
        job_id="MIL-AI-001",
        title="AI Engineer",
        company="Acme AI",
        location="Milan, Italy",
        country="Italy",
        remote_status="Hybrid",
        employment_type="Full-time",
        technologies=["Azure OpenAI"],
        application_url="https://example.com/jobs/ai",
    )

    result = score_job_match(job, profile)

    assert result["score_breakdown"]["technical_skill_match"] == 100
    assert "Azure OpenAI" in result["matched_keywords"]
    assert "Azure" not in result["matched_keywords"]
    assert "Azure" not in result["missing_requirements"]


def test_full_description_reveals_hard_experience_blocker():
    profile = build_candidate_profile()
    job = JobRecord(
        job_id="MIL-SENIOR-001",
        title="Data Engineer",
        company="Acme Data",
        location="Milan, Italy",
        country="Italy",
        remote_status="On-site",
        employment_type="Full-time",
        experience_required="UNKNOWN",
        education_required="Master's degree required",
        technologies=["Python", "SQL"],
        application_url="https://example.com/jobs/senior-data-engineer",
        full_job_description="Candidates must have 5-7 years of experience building data platforms.",
    )

    result = score_job_match(job, profile)

    assert result["tier"] == "D"
    assert result["hard_rejection_reasons"]
    assert result["score_breakdown"]["education_requirements"] == 100


def test_spelled_out_five_year_requirement_is_a_hard_blocker():
    profile = build_candidate_profile()
    job = JobRecord(
        job_id="MIL-NTT-001",
        title="AWS Data Engineer",
        company="NTT DATA",
        location="Italy",
        country="Italy",
        remote_status="UNKNOWN",
        employment_type="Full-time",
        application_url="https://example.com/jobs/aws-data-engineer",
        full_job_description="Candidates should have at least five years' experience in AWS.",
    )

    result = score_job_match(job, profile)

    assert result["tier"] == "D"
    assert "at least 5 years" in result["hard_rejection_reasons"][0]


def test_ordinary_lead_verb_in_description_does_not_imply_senior_role():
    profile = build_candidate_profile()
    job = JobRecord(
        job_id="MIL-JUNIOR-001",
        title="Junior Data Engineer",
        company="Acme Data",
        location="Milan, Italy",
        country="Italy",
        remote_status="Hybrid",
        employment_type="Full-time",
        application_url="https://example.com/jobs/junior-data-engineer",
        full_job_description="Help lead data transformation projects with Python, SQL and ETL pipelines.",
    )

    result = score_job_match(job, profile)

    assert result["score_breakdown"]["seniority_alignment"] == 95
    assert not result["hard_rejection_reasons"]
