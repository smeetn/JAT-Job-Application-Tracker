from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from app.candidate.profile import CandidateProfile, build_candidate_profile
from app.extraction.normalizer import extract_jobs_from_search_results


def build_search_queries(candidate: CandidateProfile | None = None) -> list[str]:
    profile = candidate or build_candidate_profile()
    queries = [
        "Data Engineer Milan",
        "Junior Data Engineer Milan",
        "Data Platform Engineer Milan",
        "Analytics Engineer Milan",
        "ETL Developer Milan",
        "Data Integration Engineer Milan",
        "BI Engineer Milan",
        "Oracle Data Engineer Milan",
        "AI Engineer Milan",
        "AI Data Engineer Milan",
        "Python SQL ETL Milan",
        "Python RAG Milan",
        "Oracle Data Warehouse Milan",
    ]

    if profile.technical_skills:
        for skill in ["Python", "SQL", "RAG", "Oracle", "Qdrant", "Azure OpenAI"]:
            if skill in profile.technical_skills:
                queries.append(f"{skill} Data Engineer Milan")
        queries.append("Python ETL Data Warehouse Milan")
    return queries


def load_seed_jobs(path: str | Path | None = None) -> list[dict]:
    default_path = Path(__file__).resolve().parents[2] / "data" / "jobs" / "sample_jobs.json"
    target = Path(path) if path else default_path
    return json.loads(target.read_text(encoding="utf-8"))


def _firecrawl_search(query: str) -> list[dict]:
    load_dotenv()
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return []

    try:
        from firecrawl import FirecrawlApp

        app = FirecrawlApp(api_key=api_key)
        response = app.search(query, limit=3)
        return extract_jobs_from_search_results(response)
    except Exception:
        return []


def discover_jobs(candidate: CandidateProfile | None = None, use_firecrawl: bool = True) -> list[dict]:
    load_dotenv()
    profile = candidate or build_candidate_profile()
    if use_firecrawl and os.getenv("FIRECRAWL_API_KEY"):
        discovered: list[dict] = []
        for query in build_search_queries(profile):
            discovered.extend(_firecrawl_search(query))
        if discovered:
            return discovered

    return load_seed_jobs()
