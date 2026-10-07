from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


UNKNOWN = "UNKNOWN"


@dataclass
class JobRecord:
    job_id: str
    title: str
    company: str
    location: str
    country: str
    remote_status: str
    employment_type: str
    salary: str = UNKNOWN
    salary_currency: str = UNKNOWN
    experience_required: str = UNKNOWN
    education_required: str = UNKNOWN
    technologies: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    mandatory_requirements: list[str] = field(default_factory=list)
    preferred_requirements: list[str] = field(default_factory=list)
    language_requirements: list[str] = field(default_factory=list)
    visa_work_authorization_requirements: str = UNKNOWN
    application_url: str = UNKNOWN
    source: str = UNKNOWN
    original_posting_date: str = UNKNOWN
    discovered_date: str = UNKNOWN
    closing_date: str = UNKNOWN
    company_career_url: str = UNKNOWN
    full_job_description: str = ""
    application_platform: str = UNKNOWN
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "country": self.country,
            "remote_status": self.remote_status,
            "employment_type": self.employment_type,
            "salary": self.salary,
            "salary_currency": self.salary_currency,
            "experience_required": self.experience_required,
            "education_required": self.education_required,
            "technologies": self.technologies,
            "responsibilities": self.responsibilities,
            "mandatory_requirements": self.mandatory_requirements,
            "preferred_requirements": self.preferred_requirements,
            "language_requirements": self.language_requirements,
            "visa_work_authorization_requirements": self.visa_work_authorization_requirements,
            "application_url": self.application_url,
            "source": self.source,
            "original_posting_date": self.original_posting_date,
            "discovered_date": self.discovered_date,
            "closing_date": self.closing_date,
            "company_career_url": self.company_career_url,
            "full_job_description": self.full_job_description,
            "application_platform": self.application_platform,
        }
