"""SQLite storage. One row per posting with the first and last day we saw it, and the counts
the portals report on each run."""

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from .models import FetchResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,          -- UTC timestamp
    run_date    TEXT NOT NULL           -- local date in Copenhagen
);

CREATE TABLE IF NOT EXISTS postings (
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    title         TEXT NOT NULL,
    company       TEXT,
    location      TEXT,
    latitude      REAL,
    longitude     REAL,
    url           TEXT NOT NULL,
    listed        TEXT,                 -- date shown on the listing
    deadline      TEXT,
    deadline_kind TEXT,                 -- date, asap, rolling or NULL
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS counts (
    run_id     INTEGER NOT NULL REFERENCES runs (run_id),
    source     TEXT NOT NULL,
    dimension  TEXT NOT NULL,           -- total, query or sector
    value      TEXT NOT NULL,
    count      INTEGER NOT NULL,
    PRIMARY KEY (run_id, source, dimension, value)
);

-- What was read out of each posting's own page. The ad text itself is never stored.
CREATE TABLE IF NOT EXISTS details (
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    checked_on  TEXT NOT NULL,
    status      TEXT NOT NULL,          -- ok, no_text, external, disallowed, gone or error
    language    TEXT,                   -- da or en
    danish      TEXT,                   -- required, optional or NULL when not mentioned
    hours_min   REAL,                   -- hours per week
    hours_max   REAL,
    pay_min     REAL,                   -- DKK per hour
    pay_max     REAL,
    pay_kind    TEXT,                   -- stated, agreement or NULL
    PRIMARY KEY (source, source_id)
);
"""

UPSERT_POSTING = """
INSERT INTO postings (source, source_id, title, company, location, latitude, longitude, url,
                      listed, deadline, deadline_kind, first_seen, last_seen)
VALUES (:source, :source_id, :title, :company, :location, :latitude, :longitude, :url,
        :listed, :deadline, :deadline_kind, :seen, :seen)
ON CONFLICT (source, source_id) DO UPDATE SET
    title = excluded.title,
    company = excluded.company,
    location = excluded.location,
    latitude = excluded.latitude,
    longitude = excluded.longitude,
    url = excluded.url,
    listed = excluded.listed,
    deadline = excluded.deadline,
    deadline_kind = excluded.deadline_kind,
    last_seen = excluded.last_seen
"""


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def start_run(conn: sqlite3.Connection, run_date: date, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    cur = conn.execute(
        "INSERT INTO runs (started_at, run_date) VALUES (?, ?)",
        (now.isoformat(timespec="seconds"), run_date.isoformat()),
    )
    return cur.lastrowid


def save(conn: sqlite3.Connection, run_id: int, run_date: date, result: FetchResult) -> None:
    with conn:
        for p in result.postings:
            row = vars(p) | {"seen": run_date.isoformat()}
            for key in ("listed", "deadline"):
                row[key] = row[key].isoformat() if row[key] else None
            conn.execute(UPSERT_POSTING, row)
        conn.executemany(
            "INSERT OR REPLACE INTO counts VALUES (?, ?, ?, ?, ?)",
            [(run_id, c.source, c.dimension, c.value, c.count) for c in result.counts],
        )
