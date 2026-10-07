from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from app.extraction.models import UNKNOWN


TECHNOLOGY_KEYWORDS = {
    "Python": ["python", "pandas", "numpy", "flask", "jupyter"],
    "SQL": ["sql", "pl/sql", "oracle sql", "query optimization"],
    "Oracle": ["oracle", "oracle db", "oracle sql developer", "obiee"],
    "ODI": ["oracle data integrator", "odi"],
    "ETL": ["etl", "elt", "data integration", "data transformation"],
    "Data Warehouse": ["data warehouse", "data warehousing", "enterprise data warehouse", "dwh"],
    "RAG": ["retrieval augmented generation", "rag"],
    "Qdrant": ["qdrant"],
    "Azure OpenAI": ["azure openai"],
    "Semantic Search": ["semantic search", "semantic similarity search"],
    "Vector Databases": ["vector databases", "vector database", "vector indexing"],
    "Power BI": ["power bi"],
    "Tableau": ["tableau"],
    "Docker": ["docker"],
    "Git": ["git", "github"],
    "LangChain": ["langchain"],
    "REST APIs": ["rest api"],
    "BI": ["obiee", "oracle bi", "business intelligence"],
    "Airflow": ["airflow"],
    "Spark": ["spark"],
    "dbt": ["dbt"],
    "Snowflake": ["snowflake"],
    "Databricks": ["databricks"],
    "BigQuery": ["bigquery"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_title(title: str) -> str:
    value = _normalize_text(title)
    return re.sub(r"\s+", " ", value).strip()


def _infer_location(raw_location: str, title: str, description: str) -> str:
    if raw_location:
        return raw_location
    text = f"{title} {description}".lower()
    if "milan" in text or "milano" in text:
        return "Milan, Italy"
    if "lombardy" in text or "lombardia" in text:
        return "Lombardy, Italy"
    if "rome" in text or "roma" in text:
        return "Rome, Italy"
    if "turin" in text or "torino" in text:
        return "Turin, Italy"
    if "italy" in text or "italia" in text:
        return "Italy"
    return UNKNOWN


def _infer_country(location: str, title: str, description: str) -> str:
    text = f"{location} {title} {description}".lower()
    if any(place in text for place in ("milan", "milano", "rome", "roma", "turin", "torino", "italy", "italia", "lombardy", "lombardia")):
        return "Italy"
    return "UNKNOWN"


def _infer_remote_status(location: str, title: str, description: str) -> str:
    text = " ".join([location or "", title or "", description or ""]).lower()
    if "remote" in text and "hybrid" in text:
        return "Remote / Hybrid"
    if "hybrid" in text:
        return "Hybrid"
    if "remote" in text:
        return "Remote"
    if "onsite" in text or "on-site" in text:
        return "On-site"
    return "UNKNOWN"


def _infer_employment_type(description: str) -> str:
    text = (description or "").lower()
    if "full-time" in text or "full time" in text:
        return "Full-time"
    if "contract" in text:
        return "Contract"
    if "temporary" in text:
        return "Temporary"
    return "UNKNOWN"


def _extract_technologies(description: str, title: str) -> list[str]:
    text = f"{title} {description}".lower()
    technologies: list[str] = []
    for skill, variants in TECHNOLOGY_KEYWORDS.items():
        if any(variant in text for variant in variants):
            technologies.append(skill)
    return technologies


def _extract_company(raw: dict[str, Any], url: str) -> str:
    for key in ["company", "company_name", "employer", "organization"]:
        value = raw.get(key)
        if value:
            return _normalize_text(value)
    host = urlparse(url).netloc.lower()
    known_hosts = {
        "careers.allianz.com": "Allianz",
        "www.accenture.com": "Accenture",
        "careers.nttdata.com": "NTT DATA",
        "careers.bcg.com": "BCG X",
    }
    for domain, company in known_hosts.items():
        if host.endswith(domain):
            return company
    return "UNKNOWN"


def _extract_url(raw: dict[str, Any]) -> str:
    for key in ["application_url", "url", "job_url", "link"]:
        value = raw.get(key)
        if value:
            return _normalize_text(value)
    return "UNKNOWN"


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def normalize_job_record(raw: dict[str, Any]) -> dict[str, Any]:
    raw = _safe_dict(raw)
    title = _normalize_title(raw.get("title") or raw.get("job_title") or "UNKNOWN")
    description = _normalize_text(raw.get("description") or raw.get("full_job_description") or "")
    url = _extract_url(raw)
    company = _extract_company(raw, url)
    raw_location = _normalize_text(raw.get("location") or raw.get("city") or "")
    location = _infer_location(raw_location, title, description)
    lookup_text = f"{title} {company} {location} {description}"

    normalized = {
        "job_id": hashlib.sha1(lookup_text.encode("utf-8")).hexdigest()[:12],
        "title": title,
        "company": company,
        "location": location,
        "country": _infer_country(location, title, description),
        "remote_status": _infer_remote_status(location, title, description),
        "employment_type": _infer_employment_type(description),
        "salary": UNKNOWN,
        "salary_currency": UNKNOWN,
        "experience_required": UNKNOWN,
        "education_required": UNKNOWN,
        "technologies": _extract_technologies(description, title),
        "responsibilities": [],
        "mandatory_requirements": [],
        "preferred_requirements": [],
        "language_requirements": [],
        "visa_work_authorization_requirements": UNKNOWN,
        "application_url": url,
        "source": _normalize_text(raw.get("source") or raw.get("provider") or "firecrawl"),
        "original_posting_date": UNKNOWN,
        "discovered_date": UNKNOWN,
        "closing_date": UNKNOWN,
        "company_career_url": UNKNOWN,
        "full_job_description": description,
        "application_platform": "UNKNOWN",
    }
    return normalized


def extract_jobs_from_search_results(results: Any) -> list[dict[str, Any]]:
    if results is None:
        return []

    if isinstance(results, list):
        entries = results
    elif hasattr(results, "web"):
        entries = list(getattr(results, "web") or [])
    elif isinstance(results, dict) and "web" in results:
        entries = list(results.get("web") or [])
    elif hasattr(results, "data"):
        entries = list(getattr(results, "data") or [])
    elif isinstance(results, dict) and "data" in results:
        entries = list(results.get("data") or [])
    else:
        entries = []

    normalized_jobs: list[dict[str, Any]] = []
    for item in entries:
        if not item:
            continue
        normalized_jobs.append(normalize_job_record(item))
    return normalized_jobs
