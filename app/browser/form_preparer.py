from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse


RISK_TERMS = (
    "salary",
    "compensation",
    "work authorization",
    "authorized to work",
    "sponsorship",
    "sponsor",
    "visa",
    "immigration",
    "notice period",
    "availability",
    "relocation",
    "relocate",
    "criminal",
    "background check",
    "disability",
    "medical",
    "health condition",
    "gender",
    "ethnicity",
    "race",
    "religion",
    "demographic",
    "consent",
    "agree to",
    "certify",
    "declaration",
    "signature",
    "login",
    "sign in",
    "signin",
)
TRUSTED_ATS_DOMAINS = (
    "myworkdayjobs.com",
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "phenompeople.com",
)
MULTI_PART_PUBLIC_SUFFIXES = {
    "co.uk",
    "org.uk",
    "com.au",
    "net.au",
    "co.in",
    "com.br",
    "com.sg",
    "com.tr",
    "co.jp",
    "com.mx",
    "co.nz",
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _field_metadata(locator: Any) -> dict[str, Any]:
    return locator.evaluate(
        """element => {
            const labels = element.labels ? Array.from(element.labels).map(label => label.innerText.trim()) : [];
            const fieldset = element.closest('fieldset');
            const legend = fieldset ? fieldset.querySelector('legend')?.innerText.trim() : '';
            return {
                tag: element.tagName.toLowerCase(),
                type: (element.type || element.tagName).toLowerCase(),
                name: element.name || '',
                id: element.id || '',
                placeholder: element.placeholder || '',
                aria_label: element.getAttribute('aria-label') || '',
                labels: labels.join(' '),
                legend: legend || '',
                required: Boolean(element.required),
                disabled: Boolean(element.disabled),
            };
        }"""
    )


def find_application_link(page: Any, job_url: str) -> dict[str, str] | None:
    employer_host = (urlparse(job_url).hostname or "").lower()
    host_parts = employer_host.split(".")
    suffix = ".".join(host_parts[-2:]) if len(host_parts) >= 2 else employer_host
    root_depth = 3 if suffix in MULTI_PART_PUBLIC_SUFFIXES else 2
    employer_root = ".".join(host_parts[-root_depth:]) if host_parts else ""
    page_url = page.url if urlparse(page.url).scheme in {"http", "https"} else job_url
    candidates = []
    for link in page.locator("a").all():
        if not link.is_visible():
            continue
        label = _normalize(" ".join([link.inner_text(), link.get_attribute("aria-label") or ""]))
        href = link.get_attribute("href")
        if not href or not any(term in label for term in ("apply", "application")):
            continue
        target = urljoin(page_url, href)
        parsed = urlparse(target)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        if not is_trusted_application_url(job_url, target):
            continue
        candidates.append({"url": target, "label": label})

    if not candidates:
        return None
    candidates.sort(key=lambda item: ("apply for this job" not in item["label"], "apply" not in item["label"]))
    return candidates[0]


def is_trusted_application_url(job_url: str, application_url: str) -> bool:
    employer_host = (urlparse(job_url).hostname or "").lower()
    target = urlparse(application_url)
    if target.scheme != "https" or not target.hostname:
        return False
    host_parts = employer_host.split(".")
    suffix = ".".join(host_parts[-2:]) if len(host_parts) >= 2 else employer_host
    root_depth = 3 if suffix in MULTI_PART_PUBLIC_SUFFIXES else 2
    employer_root = ".".join(host_parts[-root_depth:]) if host_parts else ""
    target_host = target.hostname.lower()
    return (
        target_host == employer_host
        or (employer_root and target_host.endswith("." + employer_root))
        or any(target_host == domain or target_host.endswith("." + domain) for domain in TRUSTED_ATS_DOMAINS)
    )


def is_browser_preparation_allowed(job_status: str) -> bool:
    """Only a reviewed, approved draft may be opened for assisted form filling."""
    return _normalize(job_status).upper() == "READY_TO_APPLY"


def _description(metadata: dict[str, Any]) -> str:
    return _normalize(
        " ".join(
            str(metadata.get(key, ""))
            for key in ("labels", "legend", "aria_label", "name", "id", "placeholder")
        )
    )


def _is_risky(description: str) -> bool:
    return any(term in description for term in RISK_TERMS)


def _application_field_markers(all_labels: str, compact_labels: str) -> int:
    return (
        ("first name" in all_labels or "given name" in all_labels or "firstname" in compact_labels or "nombre" in all_labels)
        + ("last name" in all_labels or "surname" in all_labels or "lastname" in compact_labels or "apellidos" in all_labels)
        + ("email" in all_labels or "correo electronico" in all_labels)
        + ("phone" in all_labels or "mobile" in all_labels or "telefono" in all_labels)
        + any(term in all_labels for term in ("resume", "cv", "curriculum", "cargar archivos"))
        + ("cover letter" in all_labels)
        + any(term in all_labels for term in ("why are you interested", "motivation", "years of experience"))
    )


def _select_application_form(page: Any) -> Any | None:
    forms = page.locator("form")
    scored_forms = []
    for form in forms.all():
        visible_fields = []
        for field in form.locator("input, textarea, select").all():
            if field.is_visible():
                metadata = _field_metadata(field)
                if metadata["type"] not in {"hidden", "submit", "button", "reset", "checkbox", "radio", "password"}:
                    visible_fields.append(_description(metadata))

        all_labels = " ".join(visible_fields)
        compact_labels = re.sub(r"[^a-z0-9]+", "", all_labels)
        scored_forms.append((_application_field_markers(all_labels, compact_labels), form))

    if not scored_forms:
        visible_fields = []
        for field in page.locator("input, textarea, select").all():
            if field.is_visible():
                metadata = _field_metadata(field)
                if metadata["type"] not in {"hidden", "submit", "button", "reset", "checkbox", "radio", "password"}:
                    visible_fields.append(_description(metadata))
        all_labels = " ".join(visible_fields)
        compact_labels = re.sub(r"[^a-z0-9]+", "", all_labels)
        has_identity_and_contact = (
            ("first name" in all_labels or "given name" in all_labels or "firstname" in compact_labels or "nombre" in all_labels)
            and ("last name" in all_labels or "surname" in all_labels or "lastname" in compact_labels or "apellidos" in all_labels)
            and ("email" in all_labels or "correo electronico" in all_labels)
        )
        if _application_field_markers(all_labels, compact_labels) >= 3 and has_identity_and_contact:
            return page
        return None

    scored_forms.sort(key=lambda item: item[0], reverse=True)
    if scored_forms[0][0] < 2:
        return None
    if len(scored_forms) > 1 and scored_forms[0][0] == scored_forms[1][0]:
        return None
    return scored_forms[0][1]


def inspect_application_form(page: Any) -> dict[str, Any]:
    fields = []
    form = _select_application_form(page)
    if form is not None:
        for locator in form.locator("input, textarea, select").all():
            if not locator.is_visible():
                continue
            metadata = _field_metadata(locator)
            fields.append({**metadata, "description": _description(metadata)})

    return {
        "page_url": page.url,
        "page_title": page.title(),
        "fields": fields,
        "form_detected": form is not None,
        "iframe_count": page.locator("iframe").count(),
        "iframe_form_support": False,
    }


def _known_answer(description: str, answers: list[dict[str, Any]], cover_letter: str = "") -> str | None:
    if "cover letter" in description:
        return cover_letter or None

    terms_by_question = {
        "current_location": ("location", "city", "where are you based"),
        "current_position": ("current position", "current role", "current title"),
        "years_experience": ("years of experience", "relevant experience", "how many years"),
        "education": ("education", "degree", "highest completed"),
        "english_proficiency": ("english proficiency", "english level"),
        "relevant_skills": ("relevant skills", "technical skills", "which skills"),
        "motivation": ("why this role", "why are you interested", "motivation", "why do you want"),
    }

    for answer in answers:
        if answer.get("approval_status") != "DRAFT" or answer.get("human_review_required"):
            continue
        answer_text = str(answer.get("answer", "")).strip()
        if not answer_text or answer_text.upper() == "UNKNOWN":
            continue
        question_id = answer.get("question_id")
        aliases = terms_by_question.get(question_id, ())
        if any(alias in description for alias in aliases):
            return answer_text
    return None


def _candidate_value(description: str, candidate_data: dict[str, str]) -> str | None:
    compact = re.sub(r"[^a-z0-9]+", "", description)
    if "email" in description or "e-mail" in description or "correo electronico" in description:
        return candidate_data.get("email")
    if "phone" in description or "telephone" in description or "mobile" in description or "telefono" in description:
        return candidate_data.get("phone")
    if "first name" in description or "given name" in description or "firstname" in compact or "nombre" in description:
        return candidate_data.get("first_name")
    if any(term in description for term in ("last name", "family name", "surname", "apellidos")) or "lastname" in compact:
        return candidate_data.get("last_name")
    if "full name" in description or description.endswith(" your name") or description == "name":
        return candidate_data.get("full_name")
    if "city" in description or "current location" in description or "where are you based" in description:
        return candidate_data.get("city")
    if "country" in description and "country code" not in description:
        return candidate_data.get("country")
    return None


def prepare_application_page(
    page: Any,
    package: dict[str, Any],
    candidate_data: dict[str, str],
    cv_path: str | Path | None,
) -> dict[str, Any]:
    inspection = inspect_application_form(page)
    form = _select_application_form(page)
    if form is None:
        return {
            "page_url": inspection["page_url"],
            "page_title": inspection["page_title"],
            "fields_filled": [],
            "skipped_fields": ["No unambiguous application form detected."],
            "cv_uploaded": False,
            "iframe_count": inspection["iframe_count"],
            "submission_performed": False,
            "final_submit_controls_left_untouched": True,
            "form_detected": False,
        }

    answers = package.get("answers", [])
    filled_fields: list[str] = []
    skipped_fields: list[str] = []
    cv_uploaded = False

    for locator in form.locator("input, textarea, select").all():
        if not locator.is_visible():
            continue
        metadata = _field_metadata(locator)
        description = _description(metadata)
        field_type = metadata["type"]

        if metadata["disabled"] or field_type in {"hidden", "submit", "button", "reset", "checkbox", "radio", "password"}:
            skipped_fields.append(description or field_type)
            continue
        if _is_risky(description):
            skipped_fields.append(description or field_type)
            continue

        if field_type == "file":
            if any(term in description for term in ("resume", "cv", "curriculum vitae")) and cv_path:
                file_path = Path(cv_path)
                if file_path.is_file():
                    locator.set_input_files(str(file_path))
                    cv_uploaded = True
                    filled_fields.append(description or "resume upload")
                else:
                    skipped_fields.append(f"{description or 'resume upload'} (file not found)")
            else:
                skipped_fields.append(description or "file upload")
            continue

        if field_type == "select-one" or metadata["tag"] == "select":
            skipped_fields.append(description or "select field")
            continue

        value = _candidate_value(description, candidate_data)
        if value is None:
            value = _known_answer(description, answers, str(package.get("cover_letter") or ""))
        if not value or value.strip().upper() == "UNKNOWN":
            skipped_fields.append(description or field_type)
            continue

        if field_type == "number":
            if "year" not in description:
                skipped_fields.append(description or field_type)
                continue
            numeric_value = re.search(r"\d+(?:\.\d+)?", value)
            if not numeric_value:
                skipped_fields.append(description or field_type)
                continue
            value = numeric_value.group(0)
        elif field_type not in {"text", "email", "tel", "url", "search", "textarea"}:
            skipped_fields.append(description or field_type)
            continue

        locator.fill(value)
        filled_fields.append(description or field_type)

    return {
        "page_url": inspection["page_url"],
        "page_title": inspection["page_title"],
        "fields_filled": filled_fields,
        "skipped_fields": skipped_fields,
        "cv_uploaded": cv_uploaded,
        "iframe_count": inspection["iframe_count"],
        "form_detected": True,
        "submission_performed": False,
        "final_submit_controls_left_untouched": True,
    }
