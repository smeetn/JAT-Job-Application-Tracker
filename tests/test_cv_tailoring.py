from app.candidate.cv_tailoring import (
    AI_DATA_ENGINEERING_CV,
    BI_DATA_ANALYTICS_CV,
    DATA_ENGINEERING_CV,
    PROFILES,
    build_tailored_cv,
    select_cv_version,
    write_tailored_cv,
)


RESUME_PATH = "data/resume/Smeet_s_Resume (1).pdf"


def test_cv_selection_prefers_documented_role_families():
    assert select_cv_version({"title": "Data Engineer"}) == "DATA_ENGINEERING_CV"
    assert select_cv_version({"title": "AI Engineer"}) == "AI_DATA_ENGINEERING_CV"
    assert select_cv_version({"title": "Oracle BI Developer"}) == "BI_DATA_ANALYTICS_CV"
    assert select_cv_version({"title": "Data Engineer", "technologies": ["Qdrant", "RAG"]}) == "AI_DATA_ENGINEERING_CV"


def test_tailored_variant_contains_only_source_supported_experience():
    variant = build_tailored_cv(RESUME_PATH, "DATA_ENGINEERING_CV")

    assert variant["name"] == "Smeet Nilvarna"
    assert "Oracle Data Integrator (ODI)" in " ".join(variant["skills"][0]["items"])
    assert any("150+ enterprise telecom reports" in bullet for role in variant["experience"] for bullet in role["bullets"])
    assert "Airflow" not in " ".join(variant["skills"][0]["items"])


def test_all_variants_validate_against_the_source_cv():
    for version in PROFILES:
        tailored = build_tailored_cv(RESUME_PATH, version)
        assert tailored["version"] == version
        assert len(tailored["experience"]) == 3
        assert len(tailored["education"]) == 2
        assert len(tailored["certifications"]) == 6


def test_each_profile_identifier_is_available_for_report_mapping():
    assert set(PROFILES) == {DATA_ENGINEERING_CV, AI_DATA_ENGINEERING_CV, BI_DATA_ANALYTICS_CV}


def test_generator_writes_an_editable_docx_to_requested_path(tmp_path):
    output_path = tmp_path / "DATA_ENGINEERING_CV.docx"

    result = write_tailored_cv(RESUME_PATH, "DATA_ENGINEERING_CV", output_path)

    assert result == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 1000
