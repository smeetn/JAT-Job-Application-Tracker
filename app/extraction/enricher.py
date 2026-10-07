from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

from app.extraction.normalizer import _extract_technologies


def merge_scraped_description(job: dict[str, Any], markdown: str) -> dict[str, Any]:
    content = " ".join((markdown or "").split())
    existing = str(job.get("full_job_description") or "")
    if not content:
        return job

    enriched = dict(job)
    apply_link = re.search(
        r"\[(?:apply(?:\s+now|\s+for\s+this\s+job)?|application)\]\((https?://[^\s)]+)",
        content,
        re.IGNORECASE,
    )
    if apply_link:
        enriched["application_form_url"] = apply_link.group(1)
    if len(content) > len(existing):
        enriched["full_job_description"] = content[:40000]
    heading = re.search(
        r"(?:^|\s)#\s+(.+?)(?=\s+(?:This job is available\b|Job Level:|Location:|Category\b|Job Description\b|Job No\.|$))",
        content,
        re.IGNORECASE,
    )
    if heading:
        title = re.sub(r"\s+", " ", heading.group(1)).strip(" #-|:")
        if title:
            enriched["title"] = title
    if re.search(r"\b(?:multiple locations|available in \d+ locations)\b", content, re.IGNORECASE):
        if not re.search(r"\b(?:Milan|Milano)\b", content, re.IGNORECASE):
            if re.search(r"\bItaly\b", content, re.IGNORECASE):
                enriched["location"] = "Italy"
                enriched["country"] = "Italy"
            else:
                enriched["location"] = "UNKNOWN"
                enriched["country"] = "UNKNOWN"
    technologies = list(job.get("technologies") or [])
    for technology in _extract_technologies(" ".join([existing, content]), str(job.get("title") or "")):
        if technology not in technologies:
            technologies.append(technology)
    enriched["technologies"] = technologies
    enriched["enrichment_status"] = "scraped" if len(content) > len(existing) else "scraped_no_new_content"
    return enriched


def enrich_job_records(jobs: list[dict]) -> list[dict]:
    load_dotenv()
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return [{**job, "enrichment_status": "skipped_no_api_key"} for job in jobs]

    from firecrawl import FirecrawlApp

    client = FirecrawlApp(api_key=api_key)
    enriched_jobs: list[dict] = []
    for job in jobs:
        url = str(job.get("application_url") or "")
        if not url.startswith(("http://", "https://")):
            enriched_jobs.append({**job, "enrichment_status": "skipped_no_url"})
            continue
        try:
            page = client.scrape_url(url, formats=["markdown"])
            markdown = getattr(page, "markdown", "") or ""
            enriched = merge_scraped_description(job, markdown)
            if enriched.get("enrichment_status") != "scraped":
                enriched["enrichment_status"] = "scraped_no_new_content"
            enriched_jobs.append(enriched)
        except Exception as error:
            enriched_jobs.append({
                **job,
                "enrichment_status": "failed",
                "enrichment_error": type(error).__name__,
            })
    return enriched_jobs
