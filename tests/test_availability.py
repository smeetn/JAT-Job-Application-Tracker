import requests

from app.tracking.availability import assess_availability
from app.tracking.db import get_jobs, update_job_availability, upsert_jobs


class _Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def _job(job_id="job-1"):
    return {
        "job_id": job_id,
        "title": "Data Engineer",
        "company": "Acme",
        "location": "Milan, Italy",
        "country": "Italy",
        "remote_status": "Hybrid",
        "employment_type": "Full-time",
        "application_url": "https://example.test/jobs/1",
    }


def test_explicit_filled_message_is_closed():
    result = assess_availability(
        "https://example.test/jobs/1",
        get=lambda *args, **kwargs: _Response(200, "We're sorry, this job has been filled."),
    )
    assert result.status == "CLOSED"


def test_network_error_is_not_mislabelled_closed():
    def failing_get(*args, **kwargs):
        raise requests.ConnectionError("offline")

    result = assess_availability("https://example.test/jobs/1", get=failing_get)
    assert result.status == "UNREACHABLE"


def test_confirmed_closed_listing_is_removed_from_active_queue(tmp_path):
    database = tmp_path / "jobs.sqlite"
    upsert_jobs([_job()], database)
    update_job_availability("job-1", "CLOSED", database)
    stored = get_jobs(database)[0]
    assert stored["availability_status"] == "CLOSED"
    assert stored["status"] == "CLOSED"
