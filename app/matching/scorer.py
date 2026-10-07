from __future__ import annotations

from app.candidate.profile import CandidateProfile
from app.extraction.models import JobRecord

import re


SKILL_ALIASES = {
    "Python": ("python", "pandas", "numpy"),
    "SQL": ("sql", "pl/sql", "postgresql", "mysql"),
    "Oracle": ("oracle", "odi", "obiee"),
    "ETL": ("etl", "elt", "data integration", "data ingestion"),
    "Data Warehouse": ("data warehouse", "data warehousing", "dwh"),
    "Data Modelling": ("data modelling", "data modeling", "data model"),
    "RAG": ("rag", "retrieval augmented generation", "retrieval-augmented generation"),
    "Qdrant": ("qdrant",),
    "Azure OpenAI": ("azure openai",),
    "Semantic Search": ("semantic search",),
    "Vector Databases": ("vector database", "vector databases", "vector indexing"),
    "Power BI": ("power bi",),
    "Tableau": ("tableau",),
    "Docker": ("docker",),
    "Git": ("git", "github"),
    "LangChain": ("langchain",),
    "REST APIs": ("rest api", "restful api"),
    "Airflow": ("airflow", "apache airflow"),
    "AWS": ("aws", "amazon web services"),
    "GCP": ("gcp", "google cloud", "bigquery"),
    "Spark": ("spark", "pyspark"),
    "dbt": ("dbt",),
    "Snowflake": ("snowflake",),
    "Databricks": ("databricks",),
    "Azure": ("azure",),
}

RESPONSIBILITY_GROUPS = {
    "data pipelines": ("pipeline", "pipelines", "etl", "elt", "ingestion", "data integration", "orchestration"),
    "data platforms": ("data warehouse", "dwh", "database", "data platform", "data model", "data modelling", "data modeling"),
    "analytics and BI": ("analytics", "reporting", "dashboard", "business intelligence", "obiee", "power bi", "tableau"),
    "AI retrieval": ("rag", "semantic search", "vector", "embedding", "retrieval", "large language model", "llm"),
    "data quality": ("data quality", "reconciliation", "validation", "data consistency", "data anomaly"),
}
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _text(value: str) -> str:
    return str(value or "").lower().replace("&", " and ")


def _has_phrase(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])", text.lower()) is not None


def _skills_in_text(text: str) -> set[str]:
    skills = {
        skill
        for skill, aliases in SKILL_ALIASES.items()
        if any(_has_phrase(text, alias) for alias in aliases)
    }
    if "Azure OpenAI" in skills:
        skills.discard("Azure")
    return skills


def _experience_years(text: str) -> tuple[int, int] | None:
    numeric_range = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:years|year|yrs|yr)\b", text)
    if numeric_range:
        return int(numeric_range.group(1)), int(numeric_range.group(2))

    numeric = re.search(r"(\d+)\s*\+?\s*(?:years|year|yrs|yr)\b", text)
    if numeric:
        years = int(numeric.group(1))
        return years, years

    words = "|".join(NUMBER_WORDS)
    spelled = re.search(rf"\b({words})\s+(?:to\s+)?(?:{words}\s+)?years?\b", text)
    if spelled:
        minimum = NUMBER_WORDS[spelled.group(1)]
        return minimum, minimum
    return None


def _candidate_skills(skills: list[str]) -> set[str]:
    canonical = {name.lower(): name for name in SKILL_ALIASES}
    aliases = {
        alias.lower(): name
        for name, values in SKILL_ALIASES.items()
        for alias in values
    }
    matched = set()
    for skill in skills:
        normalized = _text(skill).strip()
        if normalized in canonical:
            matched.add(canonical[normalized])
        elif normalized in aliases:
            matched.add(aliases[normalized])
    return matched


def _role_score(title: str, candidate: CandidateProfile) -> float:
    normalized_title = _text(title)
    if any(_text(role) in normalized_title for role in candidate.primary_role_targets):
        return 100.0
    if any(_text(role) in normalized_title for role in candidate.secondary_role_targets):
        return 82.0
    related_titles = ("data engineer", "etl", "analytics engineer", "ai engineer", "bi", "data warehouse")
    if any(term in normalized_title for term in related_titles):
        return 72.0
    return 15.0


def _seniority_score(title: str, requirement: str, years: int, description: str = "") -> float:
    title_and_requirement = _text(title + " " + requirement)
    experience_evidence = _text(requirement + " " + description)
    if re.search(r"\b(staff|principal|director|head|lead)\b", _text(title)):
        return 15.0
    requested_range = _experience_years(experience_evidence)
    if requested_range:
        minimum_years, maximum_years = requested_range
        if minimum_years >= years + 3:
            return 15.0
        if maximum_years <= years + 1:
            return 95.0
        return 55.0
    if "junior" in title_and_requirement or "entry level" in title_and_requirement:
        return 95.0
    if re.search(r"\bsenior\b", title_and_requirement):
        return 25.0
    return 65.0


def _location_score(job: JobRecord) -> float:
    location = _text(job.location)
    model = _text(job.remote_status)
    country = _text(job.country)
    if "milan" in location or "milano" in location:
        return 100.0
    if "lombardy" in location or "lombardia" in location:
        return 90.0
    if "remote" in model and ("italy" in location or "italy" in country):
        return 90.0
    if "hybrid" in model and ("italy" in location or "italy" in country):
        return 78.0
    if "italy" in location or "italy" in country:
        return 60.0
    if not location or location == "unknown":
        return 35.0
    return 20.0


def _education_score(requirement: str, candidate: CandidateProfile) -> float:
    required = _text(requirement)
    if not required or required == "unknown":
        return 70.0
    candidate_education = _text(" ".join(candidate.education))
    if "phd" in required or "doctorate" in required:
        return 30.0
    if "master" in required or "msc" in required:
        return 100.0 if "master" in candidate_education or "msc" in candidate_education else 35.0
    if "bachelor" in required or "degree" in required:
        return 100.0 if "bachelor" in candidate_education or "master" in candidate_education else 35.0
    return 60.0


def _hard_rejection_reasons(job: JobRecord, candidate: CandidateProfile) -> list[str]:
    evidence = _text(" ".join([job.title, job.experience_required, job.full_job_description]))
    requested = _experience_years(evidence)
    if requested:
        minimum_years = requested[0]
        if minimum_years >= candidate.years_of_experience + 3:
            return [f"Requires at least {minimum_years} years of experience; candidate profile documents about {candidate.years_of_experience} years."]
    return []


def _responsibility_score(text: str) -> float:
    job_groups = [name for name, terms in RESPONSIBILITY_GROUPS.items() if any(_has_phrase(text, term) for term in terms)]
    if not job_groups:
        return 45.0
    candidate_text = "ODI ETL ELT Oracle data warehouse SQL PL/SQL data transformation aggregation reconciliation validation root-cause analysis enterprise reporting OBIEE Python document ingestion semantic search retrieval Qdrant Azure OpenAI embeddings REST API vector indexing"
    matched = sum(
        any(_has_phrase(candidate_text, term) for term in RESPONSIBILITY_GROUPS[name])
        for name in job_groups
    )
    return round(matched / len(job_groups) * 100, 1)


def _experience_score(text: str, candidate: CandidateProfile) -> float:
    job_groups = [name for name, terms in RESPONSIBILITY_GROUPS.items() if any(_has_phrase(text, term) for term in terms)]
    if not job_groups:
        return 45.0
    candidate_evidence = _text(" ".join(candidate.current_profile + candidate.technical_skills))
    matched = sum(
        any(_has_phrase(candidate_evidence, term) for term in RESPONSIBILITY_GROUPS[name])
        for name in job_groups
    )
    return round(matched / len(job_groups) * 100, 1)


def score_job_match(job: JobRecord, candidate: CandidateProfile) -> dict:
    required_text = " ".join(job.mandatory_requirements + job.technologies)
    preferred_text = " ".join(job.preferred_requirements)
    description_text = " ".join([job.full_job_description, *job.responsibilities])
    detected_skills = _skills_in_text(" ".join([required_text, preferred_text, description_text, job.title]))
    candidate_skills = _candidate_skills(candidate.technical_skills)
    required_skills = _skills_in_text(required_text)
    preferred_skills = _skills_in_text(preferred_text) - required_skills
    weighted_skills = [(skill, 1.0) for skill in sorted(required_skills)] + [
        (skill, 0.5) for skill in sorted(preferred_skills)
    ]

    if weighted_skills:
        technical_score = round(
            sum(weight for skill, weight in weighted_skills if skill in candidate_skills)
            / sum(weight for _, weight in weighted_skills)
            * 100,
            1,
        )
    elif detected_skills:
        technical_score = round(len(detected_skills & candidate_skills) / len(detected_skills) * 100, 1)
    else:
        technical_score = 35.0

    evidence_text = _text(" ".join([job.title, job.full_job_description, *job.responsibilities]))
    experience_score = _experience_score(evidence_text, candidate)
    responsibilities_score = _responsibility_score(evidence_text)
    location_score = _location_score(job)
    career_score = _role_score(job.title, candidate)
    seniority_score = _seniority_score(
        job.title,
        job.experience_required,
        candidate.years_of_experience,
        job.full_job_description,
    )
    education_evidence = " ".join([job.education_required, job.full_job_description])
    education_score = _education_score(education_evidence, candidate)

    score_breakdown = {
        "technical_skill_match": technical_score,
        "relevant_experience": experience_score,
        "responsibilities_alignment": responsibilities_score,
        "location_work_model": location_score,
        "career_alignment": career_score,
        "seniority_alignment": seniority_score,
        "education_requirements": education_score,
    }
    weights = {
        "technical_skill_match": 0.30,
        "relevant_experience": 0.20,
        "responsibilities_alignment": 0.15,
        "location_work_model": 0.10,
        "career_alignment": 0.10,
        "seniority_alignment": 0.10,
        "education_requirements": 0.05,
    }
    total_score = round(sum(score_breakdown[key] * weights[key] for key in weights), 1)
    hard_rejection_reasons = _hard_rejection_reasons(job, candidate)
    if hard_rejection_reasons:
        total_score = min(total_score, 49.0)

    if hard_rejection_reasons:
        tier = "D"
    elif total_score >= 82:
        tier = "A"
    elif total_score >= 68:
        tier = "B"
    elif total_score >= 52:
        tier = "C"
    else:
        tier = "D"

    missing = sorted((required_skills | preferred_skills) - candidate_skills)
    transferable = {
        "Airflow": "ODI and ETL pipeline experience is relevant, though Airflow itself is not documented.",
        "AWS": "Oracle enterprise data platform work transfers conceptually; AWS experience is not documented.",
        "GCP": "Data warehouse experience transfers conceptually; GCP experience is not documented.",
        "Azure": "Azure OpenAI is documented; general Azure data platform experience is not established.",
        "Spark": "Python and ETL experience provide a foundation; Spark experience is not documented.",
    }

    return {
        "total_score": total_score,
        "tier": tier,
        "hard_rejection_reasons": hard_rejection_reasons,
        "score_breakdown": score_breakdown,
        "matched_keywords": sorted(detected_skills & candidate_skills),
        "strong_matches": sorted(required_skills & candidate_skills),
        "missing_requirements": missing,
        "transferable_gaps": [transferable[item] for item in missing if item in transferable],
        "notes": [
            "Scores are prioritization estimates based only on fields available in the posting.",
            "Unknown requirements are treated as unknown, not as satisfied.",
        ],
    }
