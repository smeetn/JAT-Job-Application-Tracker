from app.candidate.profile import build_candidate_profile
from app.matching.ranker import is_scoreable_job, rank_jobs


def _job(title, company="Acme", location="Milan, Italy", url="https://acme.com/careers/job/123", description=""):
    return {
        "job_id": title,
        "title": title,
        "company": company,
        "location": location,
        "country": "Italy",
        "remote_status": "Hybrid",
        "employment_type": "Full-time",
        "experience_required": "2+ years",
        "education_required": "UNKNOWN",
        "technologies": ["Python", "SQL", "ETL", "Oracle", "Data Warehouse"],
        "responsibilities": ["Build ETL pipelines", "Validate data quality"],
        "mandatory_requirements": ["Python", "SQL", "ETL"],
        "preferred_requirements": ["Airflow"],
        "application_url": url,
        "source": "company_career_page",
        "full_job_description": description or "Build Python SQL ETL pipelines for data warehouse systems.",
    }


def test_relevant_role_ranks_above_unrelated_senior_role():
    profile = build_candidate_profile()
    jobs = [
        _job("Data Engineer"),
        _job(
            "Senior Front End Engineer",
            location="London, UK",
            url="https://example.org/careers/senior-frontend",
            description="Lead React and TypeScript UI development for a global team; 8+ years required.",
        ) | {
            "technologies": [],
            "mandatory_requirements": [],
            "preferred_requirements": [],
            "responsibilities": [],
        },
    ]

    ranked = rank_jobs(jobs, profile)

    assert ranked[0]["title"] == "Data Engineer"
    assert ranked[0]["match"]["tier"] in {"A", "B"}
    assert ranked[1]["match"]["tier"] == "D"
    assert ranked[0]["match"]["score_breakdown"]["technical_skill_match"] > 0


def test_aggregator_and_profile_pages_are_not_scoreable_vacancies():
    assert not is_scoreable_job({
        "title": "Best Data Engineer Jobs in Milan 2026 | Built In",
        "company": "UNKNOWN",
        "application_url": "https://builtin.com/jobs/eu/italy/milan/data-analytics/search/data-engineer",
        "full_job_description": "Several openings listed on this page.",
    })
    assert not is_scoreable_job({
        "title": "ETL Developer - LinkedIn Profile",
        "company": "UNKNOWN",
        "application_url": "https://linkedin.com/in/person",
        "full_job_description": "Experienced ETL Developer.",
    })
