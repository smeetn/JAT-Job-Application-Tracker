from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from app.browser.form_preparer import inspect_application_form


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only inspection of an employer job/application page.")
    parser.add_argument("url")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.scheme != "https" or not parsed.netloc:
        parser.error("Only absolute HTTPS URLs are accepted.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        print(f"Page: {page.title()}")
        print(f"Final URL: {page.url}")
        print(f"HTTP status: {response.status if response else 'UNKNOWN'}")
        print(f"Page text preview: {page.locator('body').inner_text()[:1200]}")
        print(f"HTML form elements: {page.locator('form').count()}")
        print(f"Safe application form detected: {inspect_application_form(page)['form_detected']}")

        controls = page.locator("a, button, [role=button]").evaluate_all(
            """elements => elements
                .filter(element => /apply|application/i.test([
                    element.innerText,
                    element.getAttribute('aria-label'),
                    element.getAttribute('href')
                ].join(' ')))
                .map(element => ({
                    tag: element.tagName.toLowerCase(),
                    text: (element.innerText || '').trim(),
                    href: element.getAttribute('href'),
                    aria_label: element.getAttribute('aria-label')
                }))"""
        )
        print("Apply controls:")
        for control in controls:
            print(f"- {control['tag']}: {control['text'] or control['aria_label']} | {control['href']}")

        print("Visible form fields:")
        for field in page.locator("input, textarea, select").all():
            if not field.is_visible():
                continue
            metadata = field.evaluate(
                """element => ({
                    tag: element.tagName.toLowerCase(),
                    type: (element.type || element.tagName).toLowerCase(),
                    name: element.name || '',
                    labels: element.labels ? Array.from(element.labels).map(label => label.innerText.trim()).join(' ') : '',
                    aria_label: element.getAttribute('aria-label') || '',
                    form_id: element.closest('form')?.id || '',
                    parent_tag: element.parentElement?.tagName.toLowerCase() || ''
                })"""
            )
            print(f"- {metadata['tag']} ({metadata['type']}): {metadata['labels'] or metadata['aria_label'] or metadata['name']} | form={metadata['form_id']} | parent={metadata['parent_tag']}")
        browser.close()


if __name__ == "__main__":
    main()
