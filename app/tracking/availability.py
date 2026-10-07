from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import requests


EXPLICIT_CLOSED_PHRASES = (
    "job you are trying to apply for has been filled",
    "this job has been filled",
    "position has been filled",
    "job is no longer available",
    "this job is no longer available",
    "position is no longer available",
    "job opening is closed",
    "position is closed",
    "no longer accepting applications",
)

APPLY_SIGNALS = ("apply now", "apply for this job", "apply to this job", "submit application")


@dataclass(frozen=True)
class AvailabilityCheck:
    status: str
    reason: str
    http_status: int | None = None


def assess_availability(
    url: str,
    get: Callable[..., requests.Response] = requests.get,
) -> AvailabilityCheck:
    """Check a listing without guessing that an unreachable site is closed."""
    if not url.startswith(("https://", "http://")):
        return AvailabilityCheck("UNKNOWN", "No valid application URL.")
    try:
        response = get(
            url,
            timeout=20,
            allow_redirects=True,
            headers={"User-Agent": "JAT availability checker/1.0"},
        )
    except requests.RequestException as error:
        return AvailabilityCheck("UNREACHABLE", f"Request failed: {type(error).__name__}.")

    if response.status_code in {404, 410}:
        return AvailabilityCheck("CLOSED", f"Listing returned HTTP {response.status_code}.", response.status_code)
    if response.status_code >= 400:
        return AvailabilityCheck("UNREACHABLE", f"Listing returned HTTP {response.status_code}.", response.status_code)

    page_text = response.text.lower()
    if any(phrase in page_text for phrase in EXPLICIT_CLOSED_PHRASES):
        return AvailabilityCheck("CLOSED", "Employer page explicitly says the role is no longer open.", response.status_code)
    if any(signal in page_text for signal in APPLY_SIGNALS):
        return AvailabilityCheck("OPEN", "Employer page contains an application action.", response.status_code)
    return AvailabilityCheck("UNKNOWN", "Page loaded but did not provide a reliable open/closed signal.", response.status_code)
