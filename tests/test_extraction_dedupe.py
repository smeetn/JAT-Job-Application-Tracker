from app.extraction.dedupe import deduplicate_jobs
from app.extraction.normalizer import extract_jobs_from_search_results


def test_extract_jobs_from_search_results_extracts_normalized_entries():
    items = [
        {
            "title": "Data Engineer",
            "company": "Acme Data",
            "url": "https://example.com/jobs/1",
            "description": "Python, SQL, ETL, data warehouse, Milan, hybrid.",
            "location": "Milan, Italy",
            "source": "linkedin",
        }
    ]

    jobs = extract_jobs_from_search_results(items)

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Data Engineer"
    assert jobs[0]["company"] == "Acme Data"
    assert "Python" in jobs[0]["technologies"]
    assert "SQL" in jobs[0]["technologies"]


def test_missing_location_stays_unknown_instead_of_defaulting_to_milan():
    jobs = extract_jobs_from_search_results([
        {
            "title": "AI Engineer",
            "company": "Acme",
            "url": "https://example.com/jobs/ai-engineer",
            "description": "Build AI services for the company.",
        }
    ])

    assert jobs[0]["location"] == "UNKNOWN"
    assert jobs[0]["country"] == "UNKNOWN"


def test_deduplicate_jobs_keeps_preferred_url_and_removes_duplicates():
    jobs = [
        {
            "job_id": "dup-1",
            "title": "Data Engineer",
            "company": "Acme Data",
            "location": "Milan, Italy",
            "application_url": "https://example.com/jobs/1",
            "source": "LinkedIn",
            "full_job_description": "Python SQL ETL",
        },
        {
            "job_id": "dup-2",
            "title": "Data Engineer",
            "company": "Acme Data",
            "location": "Milan, Italy",
            "application_url": "https://example.com/jobs/1?source=indeed",
            "source": "Indeed",
            "full_job_description": "Python SQL ETL",
        },
        {
            "job_id": "dup-3",
            "title": "AI Data Engineer",
            "company": "Acme Data",
            "location": "Milan, Italy",
            "application_url": "https://example.com/jobs/2",
            "source": "company_site",
            "full_job_description": "RAG Azure OpenAI",
        },
    ]

    unique_jobs = deduplicate_jobs(jobs)

    assert len(unique_jobs) == 2
    assert unique_jobs[0]["application_url"] == "https://example.com/jobs/1"
