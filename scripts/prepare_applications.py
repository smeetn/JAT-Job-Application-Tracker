from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.applications.preparation import prepare_ranked_jobs


def main() -> None:
    report_path = ROOT / "data" / "reports" / "phase4_ranked_jobs.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    packages = prepare_ranked_jobs(report)

    print("MILAN JOB AGENT - APPLICATION PREPARATION")
    print(f"Draft packages prepared: {len(packages)}")
    print("Submission performed: no")
    for package in packages:
        folder = ROOT / "data" / "applications" / "prepared" / package["job_id"]
        print(f"\n{package['company']} - {package['title']} | Tier {package['tier']} | {package['match_score']}")
        print(f"CV: {package['selected_cv_path']}")
        print(f"Cover letter: {folder / 'cover_letter.md'}")
        print(f"Answer drafts: {folder / 'answers.json'}")
        print(f"Application URL: {package['application_url']}")
        print("Answers requiring your review:")
        for answer in package["answers"]:
            if answer["human_review_required"]:
                print(f"- {answer['question']}: {answer['answer']} - {answer.get('review_note', 'Review required.')}")
        print("Cover letter preview:")
        print(package["cover_letter"])


if __name__ == "__main__":
    main()
