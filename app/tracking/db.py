from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.extraction.models import JobRecord, UNKNOWN


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "database" / "schema.sql"
DB_PATH = ROOT / "data" / "job_agent.db"

JOB_STATUSES = {
    "NEW",
    "REVIEWING",
    "NOT_INTERESTED",
    "ALREADY_APPLIED",
    "PREPARING",
    "READY_TO_APPLY",
    "SUBMITTED",
    "INTERVIEW",
    "REJECTED",
    "OFFER",
    "CLOSED",
}

SUPPRESSED_JOB_STATUSES = {
    "NOT_INTERESTED",
    "ALREADY_APPLIED",
    "SUBMITTED",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
    "CLOSED",
}


def init_db(db_path: str | Path | None = None) -> Path:
    target = Path(db_path) if db_path else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)
        _ensure_column(conn, "jobs", "dedupe_key", "TEXT")
        _ensure_column(conn, "jobs", "status", "TEXT NOT NULL DEFAULT 'DISCOVERED'")
        _ensure_column(conn, "jobs", "notes", "TEXT")
        _ensure_column(conn, "jobs", "updated_at", "TEXT")
        _ensure_column(conn, "jobs", "availability_status", "TEXT NOT NULL DEFAULT 'UNKNOWN'")
        _ensure_column(conn, "jobs", "last_checked_at", "TEXT")
        _ensure_column(conn, "jobs", "status_reason", "TEXT")
        _ensure_column(conn, "jobs", "status_updated_at", "TEXT")
        _ensure_column(conn, "applications", "submitted_date_precision", "TEXT NOT NULL DEFAULT 'UNKNOWN'")
        _ensure_column(conn, "applications", "status_reason", "TEXT")
        conn.execute("UPDATE jobs SET status = 'NEW' WHERE status = 'DISCOVERED'")
        conn.execute("UPDATE jobs SET status = 'REVIEWING' WHERE status = 'ANALYZED'")
        conn.execute("UPDATE jobs SET status = 'READY_TO_APPLY' WHERE status = 'AWAITING_APPROVAL'")
        conn.execute("UPDATE applications SET status = 'READY_TO_APPLY' WHERE status = 'AWAITING_APPROVAL'")
        conn.execute("UPDATE jobs SET status_updated_at = COALESCE(status_updated_at, updated_at, created_at, CURRENT_TIMESTAMP)")
        conn.execute("UPDATE jobs SET dedupe_key = job_id WHERE dedupe_key IS NULL")
        conn.execute("UPDATE jobs SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_dedupe_key ON jobs(dedupe_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_availability_status ON jobs(availability_status)")
        _merge_duplicate_url_rows(conn)
    return target


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _normalize_identity(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return re.sub(r"\bmilano\b", "milan", normalized)


def _canonical_url(value: str) -> str:
    if not value or value == UNKNOWN:
        return ""
    parsed = urlsplit(value.strip())
    ignored = {"trk", "ref", "source", "utm_campaign", "utm_medium", "utm_source", "utm_term", "utm_content"}
    query = urlencode(
        [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() not in ignored]
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/").lower(), query, ""))


def _merge_duplicate_url_rows(conn: sqlite3.Connection) -> None:
    jobs = conn.execute(
        "SELECT rowid AS _rowid, * FROM jobs WHERE application_url IS NOT NULL AND application_url != 'UNKNOWN' "
        "ORDER BY updated_at DESC, created_at DESC, rowid DESC"
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for job in jobs:
        canonical_url = _canonical_url(job["application_url"])
        if canonical_url:
            grouped.setdefault(canonical_url, []).append(job)

    application_counts = {
        row["job_id"]: row["count"]
        for row in conn.execute("SELECT job_id, COUNT(*) AS count FROM applications GROUP BY job_id")
    }
    merge_columns = [
        column
        for column in JOB_FIELDS
        if column not in {"job_id", "application_url"}
    ]

    for duplicates in grouped.values():
        if len(duplicates) < 2:
            continue
        keeper = max(
            duplicates,
            key=lambda job: (
                application_counts.get(job["job_id"], 0) > 0,
                job["updated_at"] or "",
                job["created_at"] or "",
            ),
        )
        latest = max(duplicates, key=lambda job: (job["updated_at"] or "", job["created_at"] or "", job["_rowid"]))
        update_values = {
            column: latest[column]
            for column in merge_columns
            if latest[column] is not None
            and (not isinstance(latest[column], str) or latest[column].strip().upper() != UNKNOWN)
        }
        update_values["updated_at"] = "CURRENT_TIMESTAMP"
        assignments = [
            f"{column} = {value}" if column == "updated_at" else f"{column} = ?"
            for column, value in update_values.items()
        ]
        values = [value for column, value in update_values.items() if column != "updated_at"]
        if assignments:
            conn.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id = ?",
                (*values, keeper["job_id"]),
            )

        for duplicate in duplicates:
            if duplicate["job_id"] == keeper["job_id"]:
                continue
            conn.execute(
                "UPDATE applications SET job_id = ? WHERE job_id = ?",
                (keeper["job_id"], duplicate["job_id"]),
            )
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (duplicate["job_id"],))


def _dedupe_key(job: dict) -> str:
    canonical_url = _canonical_url(job.get("application_url", ""))
    if canonical_url:
        return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
    company = _normalize_identity(job.get("company", ""))
    title = _normalize_identity(job.get("title", ""))
    location = _normalize_identity(job.get("location", ""))
    if company and title and company != "unknown" and title != "unknown":
        identity = "|".join((company, title, location or "unknown"))
    else:
        identity = _canonical_url(job.get("application_url", "")) or str(job.get("job_id", "unknown"))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def serialize_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def deserialize_list(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else [raw]
    except json.JSONDecodeError:
        return [raw]


LIST_FIELDS = {
    "technologies",
    "responsibilities",
    "mandatory_requirements",
    "preferred_requirements",
    "language_requirements",
}
JOB_FIELDS = [field for field in JobRecord.__dataclass_fields__ if field != "score"]


def upsert_jobs(jobs: list[dict], db_path: str | Path | None = None) -> dict[str, int]:
    target = init_db(db_path)
    inserted = 0
    updated = 0
    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        for job in jobs:
            dedupe_key = _dedupe_key(job)
            existing = conn.execute(
                "SELECT job_id, dedupe_key FROM jobs WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
            canonical_url = _canonical_url(job.get("application_url", ""))
            if existing is None and canonical_url:
                for candidate in conn.execute(
                    "SELECT job_id, dedupe_key, application_url FROM jobs WHERE application_url IS NOT NULL"
                ):
                    if _canonical_url(candidate["application_url"]) == canonical_url:
                        existing = candidate
                        break
            record = {field: job.get(field, UNKNOWN) for field in JOB_FIELDS}
            record_job_id = (existing["job_id"] if existing else job.get("job_id")) or dedupe_key[:12]
            if not existing and conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (record_job_id,)).fetchone():
                digest_length = 12
                while digest_length <= len(dedupe_key):
                    record_job_id = dedupe_key[:digest_length]
                    if not conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (record_job_id,)).fetchone():
                        break
                    digest_length += 4
                else:
                    raise RuntimeError("Could not allocate a unique job ID for the discovered record.")
            record["job_id"] = record_job_id
            record["dedupe_key"] = (existing["dedupe_key"] if existing else None) or dedupe_key
            record["status"] = job.get("status", "NEW")
            record["notes"] = job.get("notes")
            record["score"] = job.get("score")

            columns = ["job_id", "dedupe_key", *JOB_FIELDS[1:], "score", "status", "notes"]
            values = []
            for column in columns:
                value = record.get(column)
                if column in LIST_FIELDS:
                    value = serialize_list(value if isinstance(value, list) else [])
                values.append(value)

            updates = [
                f"{column} = excluded.{column}"
                for column in columns
                if column not in {"job_id", "dedupe_key", "status", "score", "notes"}
            ]
            updates.extend([
                "status = CASE WHEN jobs.status = 'NEW' THEN excluded.status ELSE jobs.status END",
                "score = COALESCE(excluded.score, jobs.score)",
                "notes = COALESCE(excluded.notes, jobs.notes)",
                "updated_at = CURRENT_TIMESTAMP",
            ])
            conn.execute(
                f"INSERT INTO jobs ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) "
                f"ON CONFLICT(dedupe_key) DO UPDATE SET {', '.join(updates)}",
                values,
            )
            if existing:
                updated += 1
            else:
                inserted += 1
    return {"inserted": inserted, "updated": updated}


def get_jobs(db_path: str | Path | None = None, status: str | None = None) -> list[dict]:
    target = init_db(db_path)
    query = "SELECT * FROM jobs"
    parameters: tuple[str, ...] = ()
    if status:
        query += " WHERE status = ?"
        parameters = (status,)
    query += " ORDER BY created_at, job_id"
    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, parameters).fetchall()
    jobs = [dict(row) for row in rows]
    for job in jobs:
        for field in LIST_FIELDS:
            job[field] = deserialize_list(job[field])
    return jobs


def set_job_status(
    job_id: str,
    status: str,
    score: float | None = None,
    notes: str | None = None,
    reason: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    target = init_db(db_path)
    normalized_status = status.strip().upper()
    if normalized_status not in JOB_STATUSES:
        supported = ", ".join(sorted(JOB_STATUSES))
        raise ValueError(f"Unsupported job status: {status}. Supported statuses: {supported}")
    with sqlite3.connect(str(target)) as conn:
        cursor = conn.execute(
            "UPDATE jobs SET status = ?, score = COALESCE(?, score), notes = COALESCE(?, notes), "
            "status_reason = COALESCE(?, status_reason), status_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (normalized_status, score, notes, reason, job_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Job not found: {job_id}")


def save_analysis_results(jobs: list[dict], db_path: str | Path | None = None) -> dict[str, int]:
    records = []
    for job in jobs:
        match = job.get("match", {})
        record = {field: job.get(field, UNKNOWN) for field in JOB_FIELDS}
        record.update(
            {
                "score": match.get("total_score", job.get("score")),
                "status": "REVIEWING",
                "notes": json.dumps(
                    {
                        "tier": match.get("tier", UNKNOWN),
                        "review_required": match.get("review_required", True),
                        "hard_rejection_reasons": match.get("hard_rejection_reasons", []),
                        "recommended_cv": job.get("recommended_cv", UNKNOWN),
                    },
                    ensure_ascii=False,
                ),
            }
        )
        records.append(record)
    return upsert_jobs(records, db_path)


def save_prepared_application(
    job_id: str,
    cv_version: str,
    cover_letter: str,
    answers: list[dict],
    notes: dict,
    db_path: str | Path | None = None,
) -> int:
    target = init_db(db_path)
    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        job = conn.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not job:
            raise KeyError(f"Job not found: {job_id}")

        existing = conn.execute(
            "SELECT id, status FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if existing and existing["status"] not in {"PREPARING", "READY_TO_APPLY"}:
            raise ValueError(
                f"An application for {job_id} already progressed to {existing['status']}; refusing to overwrite it."
            )

        values = (
            cv_version,
            cover_letter,
            json.dumps(answers, ensure_ascii=False),
            date.today().isoformat(),
            "READY_TO_APPLY",
            json.dumps(notes, ensure_ascii=False),
        )
        if existing:
            application_id = existing["id"]
            conn.execute(
                "UPDATE applications SET cv_version = ?, cover_letter = ?, answers = ?, date_prepared = ?, status = ?, notes = ? WHERE id = ?",
                (*values, application_id),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO applications (job_id, cv_version, cover_letter, answers, date_prepared, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, *values),
            )
            application_id = cursor.lastrowid

        conn.execute(
            "UPDATE jobs SET status = 'READY_TO_APPLY', status_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (job_id,),
        )
        return int(application_id)


APPLICATION_EXCLUSION_STATUSES = {
    "SUBMITTED",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
}


def set_application_status(
    job_id: str,
    status: str,
    submitted_date: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    target = init_db(db_path)
    normalized_status = status.strip().upper()
    allowed_statuses = APPLICATION_EXCLUSION_STATUSES | {"PREPARING", "READY_TO_APPLY"}
    if normalized_status not in allowed_statuses:
        raise ValueError(f"Unsupported application status: {status}")

    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        application = conn.execute(
            "SELECT id FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if not application:
            raise KeyError(f"Application not found for job: {job_id}")
        conn.execute(
            "UPDATE applications SET status = ?, date_submitted = CASE WHEN ? = 'SUBMITTED' THEN ? ELSE date_submitted END WHERE id = ?",
            (normalized_status, normalized_status, submitted_date, application["id"]),
        )
        conn.execute(
            "UPDATE jobs SET status = ?, status_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (normalized_status, job_id),
        )


def record_historical_application(
    job_id: str,
    applied_date: str | None,
    date_precision: str,
    reason: str,
    db_path: str | Path | None = None,
) -> int:
    """Record a past application without pretending its approximate date is exact."""
    target = init_db(db_path)
    normalized_precision = date_precision.strip().upper()
    if normalized_precision not in {"EXACT", "MONTH", "UNKNOWN"}:
        raise ValueError("date_precision must be EXACT, MONTH, or UNKNOWN.")
    with sqlite3.connect(str(target)) as conn:
        job = conn.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        cursor = conn.execute(
            "INSERT INTO applications (job_id, date_submitted, submitted_date_precision, status, status_reason, notes) "
            "VALUES (?, ?, ?, 'SUBMITTED', ?, ?)",
            (job_id, applied_date, normalized_precision, reason, "Recorded from application history."),
        )
        conn.execute(
            "UPDATE jobs SET status = 'ALREADY_APPLIED', status_reason = ?, status_updated_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (reason, job_id),
        )
        return int(cursor.lastrowid)


def get_previously_applied_jobs(db_path: str | Path | None = None) -> list[dict]:
    target = init_db(db_path)
    statuses = sorted(APPLICATION_EXCLUSION_STATUSES)
    placeholders = ", ".join("?" for _ in statuses)
    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT j.*, a.status AS application_status FROM applications a "
            f"JOIN jobs j ON j.job_id = a.job_id WHERE a.status IN ({placeholders}) "
            "ORDER BY a.id DESC",
            statuses,
        ).fetchall()
    records = [dict(row) for row in rows]
    for record in records:
        for field in LIST_FIELDS:
            record[field] = deserialize_list(record[field])
    return records


def get_suppressed_jobs(db_path: str | Path | None = None) -> list[dict]:
    """Return jobs that must not re-enter the active recommendation queue."""
    target = init_db(db_path)
    statuses = sorted(SUPPRESSED_JOB_STATUSES)
    placeholders = ", ".join("?" for _ in statuses)
    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY updated_at DESC, job_id",
            statuses,
        ).fetchall()
    records = [dict(row) for row in rows]
    for record in records:
        record["application_status"] = record["status"]
        for field in LIST_FIELDS:
            record[field] = deserialize_list(record[field])
    return records


def update_job_availability(
    job_id: str,
    availability_status: str,
    db_path: str | Path | None = None,
) -> None:
    """Persist a conservative availability result and close only confirmed closed roles."""
    allowed = {"OPEN", "CLOSED", "UNKNOWN", "UNREACHABLE"}
    normalized = availability_status.strip().upper()
    if normalized not in allowed:
        raise ValueError(f"Unsupported availability status: {availability_status}")
    target = init_db(db_path)
    with sqlite3.connect(str(target)) as conn:
        cursor = conn.execute(
            "UPDATE jobs SET availability_status = ?, last_checked_at = CURRENT_TIMESTAMP, "
            "status = CASE WHEN ? = 'CLOSED' AND status NOT IN ('ALREADY_APPLIED', 'NOT_INTERESTED') "
            "THEN 'CLOSED' ELSE status END, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (normalized, normalized, job_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Job not found: {job_id}")
