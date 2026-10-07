from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


def find_latest_resume(path: str | Path) -> Path:
    resume_path = Path(path)
    if resume_path.is_file():
        return resume_path
    if not resume_path.is_dir():
        raise FileNotFoundError(f"Resume path not found: {resume_path}")

    candidates = [
        file_path
        for pattern in ("*.pdf", "*.txt", "*.md")
        for file_path in resume_path.glob(pattern)
    ]
    if not candidates:
        raise FileNotFoundError(f"No supported resume file found in: {resume_path}")
    return max(candidates, key=lambda file_path: (file_path.stat().st_mtime_ns, file_path.name.lower()))


def extract_resume_text(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Resume not found: {path}")

    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"Unsupported resume format: {path.suffix}")


def extract_contact_details(text: str) -> dict[str, str]:
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE)
    phone_match = re.search(r"\+\d{1,3}(?:[\s().-]*\d){7,14}", text)
    return {
        "email": email_match.group(0).strip() if email_match else "",
        "phone": re.sub(r"\s+", " ", phone_match.group(0)).strip() if phone_match else "",
    }


def extract_resume_summary(path: str | Path) -> dict:
    resolved_path = find_latest_resume(path)
    text = extract_resume_text(resolved_path)
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    name = normalized.splitlines()[0].strip() if normalized else "UNKNOWN"

    keywords = {
        "Python": ["python", "pandas", "numpy", "flask", "jupyter"],
        "SQL": ["sql", "pl/sql", "oracle sql", "query optimization"],
        "Oracle": ["oracle", "oracle db", "oracle sql developer", "obiee"],
        "ODI": ["oracle data integrator", "odi"],
        "ETL": ["etl", "elt", "data integration", "data transformation"],
        "Data Warehousing": ["data warehouse", "data warehousing", "enterprise data warehouse", "dwh"],
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
        "REST APIs": ["rest api", "rest api"],
        "BI": ["obiee", "oracle bi", "business intelligence"],
    }

    matched_skills = []
    lower_text = text.lower()
    for skill, variants in keywords.items():
        if any(variant in lower_text for variant in variants):
            matched_skills.append(skill)

    return {
        "name": name,
        "text": text,
        "contact_details": extract_contact_details(text),
        "skills": matched_skills,
        "years_experience": 2,
        "resume_path": str(resolved_path),
    }
