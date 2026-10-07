from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.candidate.resume_parser import extract_resume_summary, find_latest_resume


@dataclass
class CandidateProfile:
    name: str
    current_location: str
    target_locations: list[str]
    years_of_experience: int
    current_profile: list[str]
    strongest_directions: list[str]
    technical_skills: list[str]
    primary_role_targets: list[str]
    secondary_role_targets: list[str]
    education: list[str]
    weaknesses: list[str]
    preferred_remote_status: list[str] = field(default_factory=lambda: ["Remote", "Hybrid"])
    work_authorization: str = "UNKNOWN"
    languages: dict[str, str] = field(default_factory=lambda: {"English": "Professional", "Italian": "Basic"})
    notes: dict[str, Any] = field(default_factory=dict)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = ROOT / "data" / "candidate" / "candidate_profile.json"


def _load_profile(path: str | Path | None = None) -> dict[str, Any]:
    profile_path = Path(path) if path else DEFAULT_PROFILE_PATH
    try:
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Candidate profile not found: {profile_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Candidate profile is not valid JSON: {profile_path}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"Candidate profile must be a JSON object: {profile_path}")
    return raw


def _list_value(profile: dict[str, Any], key: str) -> list[str]:
    value = profile.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Candidate profile field '{key}' must be a list of strings.")
    return value


def build_candidate_profile(
    resume_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> CandidateProfile:
    """Build the active profile from editable JSON, augmented with CV-detected skills."""
    configured = _load_profile(profile_path)
    default_resume = Path(__file__).resolve().parents[2] / "data" / "resume"
    resume_file = Path(resume_path) if resume_path is not None else default_resume

    technical_skills = _list_value(configured, "technical_skills")
    name = str(configured.get("name") or "UNKNOWN")
    years_of_experience = int(configured.get("years_of_experience", 0))
    if not name or name == "UNKNOWN" or years_of_experience < 0:
        raise ValueError("Candidate profile requires a name and a non-negative years_of_experience value.")

    try:
        resume_file = find_latest_resume(resume_file)
        summary = extract_resume_summary(resume_file)
        technical_skills = sorted({*technical_skills, *summary.get("skills", [])})
        if name == "UNKNOWN" and summary.get("name"):
            name = summary["name"]
    except (FileNotFoundError, ValueError):
        pass

    notes = dict(configured.get("notes") or {})
    notes["resume_path"] = str(resume_file)
    notes["profile_path"] = str(Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH)

    return CandidateProfile(
        name=name,
        current_location=str(configured.get("current_location") or "UNKNOWN"),
        target_locations=_list_value(configured, "target_locations"),
        years_of_experience=years_of_experience,
        current_profile=_list_value(configured, "current_profile"),
        strongest_directions=_list_value(configured, "strongest_directions"),
        technical_skills=technical_skills,
        primary_role_targets=_list_value(configured, "primary_role_targets"),
        secondary_role_targets=_list_value(configured, "secondary_role_targets"),
        education=_list_value(configured, "education"),
        weaknesses=_list_value(configured, "weaknesses"),
        preferred_remote_status=_list_value(configured, "preferred_remote_status") or ["Remote", "Hybrid"],
        work_authorization=str(configured.get("work_authorization") or "UNKNOWN"),
        languages=dict(configured.get("languages") or {}),
        notes=notes,
    )
