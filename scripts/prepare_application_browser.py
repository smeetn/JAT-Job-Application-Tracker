from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.browser.form_preparer import (
    find_application_link,
    inspect_application_form,
    is_browser_preparation_allowed,
    is_trusted_application_url,
    prepare_application_page,
)
from app.candidate.profile import build_candidate_profile
from app.candidate.resume_parser import extract_resume_summary, find_latest_resume
from app.tracking.db import get_jobs


def _load_package(job_id: str) -> tuple[dict, Path]:
    package_path = ROOT / "data" / "applications" / "prepared" / job_id / "preparation.json"
    if not package_path.is_file():
        raise FileNotFoundError(f"Prepared application not found for job_id {job_id}.")
    return json.loads(package_path.read_text(encoding="utf-8")), package_path


def _candidate_data(resume_path: Path) -> dict[str, str]:
    summary = extract_resume_summary(resume_path)
    full_name = summary["name"].strip()
    name_parts = full_name.split()
    profile = build_candidate_profile(resume_path)
    contacts = summary.get("contact_details", {})
    city, _, country = profile.current_location.partition(",")
    return {
        "full_name": full_name,
        "first_name": name_parts[0] if name_parts else "",
        "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
        "email": contacts.get("email", ""),
        "phone": contacts.get("phone", ""),
        "city": city.strip(),
        "country": country.strip(),
    }


def _contains_captcha(page) -> bool:
    captcha_frame = page.locator('iframe[src*="captcha"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').count()
    body = page.locator("body").inner_text().lower()
    return captcha_frame > 0 or "verify you are human" in body or "captcha" in body


def _wait_for_hydration(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect and safely prepare an application form; never submits it.")
    parser.add_argument("job_id", help="Job ID from the prepared application package")
    parser.add_argument("--open", action="store_true", help="Open the employer page visibly and fill safe, known fields")
    arguments = parser.parse_args()

    try:
        package, package_path = _load_package(arguments.job_id)
    except FileNotFoundError as error:
        parser.error(str(error))

    tracked_job = next((job for job in get_jobs() if job["job_id"] == arguments.job_id), None)
    if tracked_job is None:
        parser.error("The prepared package has no matching tracked job.")
    if not is_browser_preparation_allowed(tracked_job["status"]):
        parser.error(
            f"Browser preparation requires READY_TO_APPLY status; this job is {tracked_job['status']}."
        )

    cv_path = Path(package["selected_cv_path"])
    if not cv_path.is_absolute():
        cv_path = ROOT / cv_path
    resume_path = find_latest_resume(ROOT / "data" / "resume")
    candidate = _candidate_data(resume_path)
    url = str(package.get("application_url") or "")
    if urlparse(url).scheme not in {"http", "https"} or not urlparse(url).netloc:
        parser.error("The saved application URL is missing or invalid.")

    print(f"Job: {package['company']} - {package['title']}")
    print(f"Selected CV: {cv_path}")
    print(f"Saved draft package: {package_path.parent}")
    print("Unknown and high-risk answers will be skipped. The final submit control will not be used.")

    if not arguments.open:
        print(f"Dry run only. No browser opened and no site contacted. Target: {url}")
        print("Add --open to open a visible browser and prepare the form for your review.")
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        application_form_url = str(package.get("application_form_url") or "")
        start_url = url
        if application_form_url and application_form_url.upper() != "UNKNOWN":
            if is_trusted_application_url(url, application_form_url):
                start_url = application_form_url
                print(f"Opening verified application form URL: {start_url}")
            else:
                print("Ignored an untrusted application-form URL from page data.")

        page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
        _wait_for_hydration(page)

        if _contains_captcha(page):
            print("CAPTCHA detected. Stopped without interacting; complete it yourself if you choose.")
            browser.close()
            return
        application_link = None
        if not inspect_application_form(page)["form_detected"]:
            application_link = find_application_link(page, url)
        if application_link:
            print(f"Navigating to trusted application link: {application_link['url']}")
            page.goto(application_link["url"], wait_until="domcontentloaded", timeout=60000)
            _wait_for_hydration(page)
            if _contains_captcha(page):
                print("CAPTCHA detected on the application page. Stopped without interacting.")
                browser.close()
                return
            if page.locator('input[type="password"]').count() > 0 and not inspect_application_form(page)["form_detected"]:
                print("Login/password form detected. Stopped without attempting authentication.")
                browser.close()
                return
        elif not inspect_application_form(page)["form_detected"]:
            print("No trusted Apply link or unambiguous application form found. Stopped without filling fields.")
            browser.close()
            return

        if page.locator('input[type="password"]').count() > 0 and not inspect_application_form(page)["form_detected"]:
            print("Login/password form detected. Stopped without attempting authentication.")
            browser.close()
            return

        if page.locator("input, textarea, select").count() == 0 and page.locator("iframe").count() > 0:
            print("The application form appears to be inside an iframe, which this helper does not fill. Stopped for manual review.")
            browser.close()
            return

        result = prepare_application_page(page, package, candidate, cv_path if cv_path.is_file() else None)
        audit_path = package_path.parent / "browser_preparation.json"
        audit_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Fields filled: {len(result['fields_filled'])}")
        for field in result["fields_filled"]:
            print(f"- {field}")
        print(f"Fields skipped for review/unsupported controls: {len(result['skipped_fields'])}")
        for field in result["skipped_fields"]:
            print(f"- {field}")
        print(f"Selected CV uploaded: {result['cv_uploaded']}")
        print(f"Field audit: {audit_path}")
        print("Submission performed: no")
        print("Review the visible browser. Do not submit unless you have reviewed and approved the application.")
        try:
            input("Press Enter here to close the browser: ")
        except EOFError:
            pass
        browser.close()


if __name__ == "__main__":
    main()
