# Milan Job Agent

A lightweight personal recruiting system for structured job discovery, matching, application preparation, and tracking in Milan.

## Implemented phases

- Phase 1: parse the uploaded CV into a structured candidate profile.
- Phase 2: build Milan-focused search queries and discover results with Firecrawl.
- Phase 3: normalize Firecrawl results into job records and deduplicate repeated results.
- Phase 4: score individual vacancies against the profile and report weighted fit, missing skills, confidence, and excluded non-vacancy pages.
- Phase 5: persist discovered and analyzed jobs in SQLite, deduplicate across runs, and preserve workflow status and prior scores.
- Phase 6: generate three editable, role-focused CV variants from the uploaded source CV, with source-text checks on experience and project bullets.
- Phase 7: prepare role-specific cover letters and draft screening answers for Tier A/B jobs without submitting applications.
- Phase 8: visibly inspect and safely fill recognized application forms using known candidate data; skip unknown/high-risk controls and never submit.
- Final approval UI and outcome learning remain future work.

## Project layout

- `app/candidate/`: candidate profile and strengths/gaps analysis
- `app/discovery/`: job discovery and search term generation
- `app/extraction/`: normalized job extraction models
- `app/matching/`: role compatibility assessment and ranking
- `app/applications/`: CV selection, cover letters, and answer drafts
- `app/tracking/`: persistence layer for job and application history
- `database/`: schema and SQLite setup
- `data/`: candidate profile and seed job data
- `scripts/`: operational scripts
- `tests/`: regression tests for the matching engine

## Quick start

```bash
python -m pip install -r requirements.txt
python scripts/generate_initial_report.py
python scripts/run_phase3.py
python scripts/run_phase4.py
python scripts/check_job_availability.py
python scripts/generate_tailored_cvs.py
python scripts/prepare_applications.py
python scripts/prepare_application_browser.py <job_id>
```

`run_phase3.py` requires `FIRECRAWL_API_KEY` in `.env`. It saves a JSON export and upserts discovered results into `data/job_agent.db`. `run_phase4.py` enriches and ranks the most recently discovered data, saves the report to `data/reports/phase4_ranked_jobs.json`, and updates analyzed job scores/statuses in the same database. Re-running either step updates existing records instead of creating duplicates.

`data/candidate/candidate_profile.json` is the editable source of truth for your location, experience, target roles, skills, languages, work authorization, and preferences. The résumé only adds detected skill keywords; it does not override the JSON profile's personal facts.

The job lifecycle is `NEW`, `REVIEWING`, `NOT_INTERESTED`, `ALREADY_APPLIED`, `PREPARING`, `READY_TO_APPLY`, `SUBMITTED`, `INTERVIEW`, `REJECTED`, `OFFER`, or `CLOSED`. Re-discovery refreshes job details but never overwrites a status after `NEW`.

Use `python scripts/set_job_status.py <job_id> ALREADY_APPLIED --reason "Applied before using this tracker"` to permanently suppress a tracked role. For an older application that is not yet in the database, use `python scripts/record_prior_application.py "Junior Data Engineer" "Accenture" --location "Milan, Italy" --applied-date "2026-06" --date-precision MONTH`. The stored application keeps both the approximate date and its precision, plus the reason. `NOT_INTERESTED` and `CLOSED` are also suppressed. `python scripts/check_job_availability.py` checks active saved URLs: it marks a role `CLOSED` only when a page explicitly says so or returns HTTP 404/410; inaccessible or ambiguous pages remain visible as `UNREACHABLE` or `UNKNOWN` rather than being incorrectly discarded.

`generate_tailored_cvs.py` writes `DATA_ENGINEERING_CV.docx`, `AI_DATA_ENGINEERING_CV.docx`, and `BI_DATA_ANALYTICS_CV.docx` under `data/candidate/cvs/`. Phase 4 recommendations use those same profile IDs and filenames. Keep the latest source CV in `data/resume/`; the most recently modified supported file is selected.

`prepare_applications.py` prepares packages only for Tier A/B opportunities without hard-rejection reasons. It writes the cover letter, draft answers, and preparation summary under `data/applications/prepared/<job_id>/`, stores the record as `READY_TO_APPLY`, and never submits or fills a web form. Unknown salary, notice-period, work-authorization, sponsorship, Italian-proficiency, and relocation answers are flagged for candidate review.

`prepare_application_browser.py <job_id>` is a dry run by default: it does not open a browser or contact the site. It only operates on a job whose database status is `READY_TO_APPLY`. Add `--open` to launch a visible Chromium window. It follows only a recognizable HTTPS Apply link on the employer domain or a supported ATS, or uses a directly loaded page with an unambiguous application form. It fills confirmed fields, may upload only the selected CV, skips checkboxes/selects and high-risk or unknown questions, stops on login/CAPTCHA, and never clicks submit. It writes a field-label-only audit to the prepared package; no entered values are logged. Review the visible page yourself and close it without submitting until you approve every entry.

Fit scores are heuristics for prioritization, not hiring probabilities. When the posting omits facts, the report keeps them unknown and flags low-confidence records for review.

## Notes

This is intentionally incremental and follows the system architecture described in the master prompt. The project starts with a validated baseline rather than broad automation without evidence.
