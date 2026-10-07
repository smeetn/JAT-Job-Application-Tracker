from app.candidate.profile import build_candidate_profile
from app.candidate.resume_parser import find_latest_resume


def test_candidate_profile_uses_uploaded_resume_when_available():
    profile = build_candidate_profile("data/resume/Smeet_s_Resume (1).pdf")

    assert profile.name == "Smeet Nilvarna"
    assert "Python" in profile.technical_skills
    assert "Oracle" in profile.technical_skills
    assert "RAG" in profile.technical_skills
    assert "Qdrant" in profile.technical_skills


def test_resume_folder_uses_most_recent_supported_file(tmp_path):
    older = tmp_path / "resume_old.pdf"
    newer = tmp_path / "resume_latest.pdf"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    older.touch()
    newer.touch()

    import os

    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    assert find_latest_resume(tmp_path) == newer


def test_candidate_profile_uses_editable_json_values(tmp_path):
    profile_file = tmp_path / "candidate.json"
    profile_file.write_text(
        '''{
          "name": "Editable Candidate",
          "current_location": "Turin, Italy",
          "target_locations": ["Turin"],
          "years_of_experience": 4,
          "current_profile": ["Data Engineer"],
          "strongest_directions": ["Data Engineer"],
          "technical_skills": ["Python"],
          "primary_role_targets": ["Data Engineer"],
          "secondary_role_targets": [],
          "education": ["MSc"],
          "weaknesses": [],
          "preferred_remote_status": ["Hybrid"],
          "work_authorization": "Italy",
          "languages": {"English": "Professional"}
        }''',
        encoding="utf-8",
    )

    profile = build_candidate_profile(resume_path=tmp_path / "missing", profile_path=profile_file)

    assert profile.name == "Editable Candidate"
    assert profile.current_location == "Turin, Italy"
    assert profile.years_of_experience == 4
    assert profile.work_authorization == "Italy"
