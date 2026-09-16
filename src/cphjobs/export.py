"""CSV exports for the dashboard. Power BI reads these from their raw GitHub URLs, which lets
the published report refresh on its own without a gateway."""

import csv
import sqlite3
from pathlib import Path

QUERIES = {
    "postings.csv": """
        SELECT source, source_id, title, company, location, latitude, longitude, url,
               listed, deadline, deadline_kind, first_seen, last_seen
        FROM postings
        ORDER BY first_seen DESC, source, source_id
    """,
    # One row per day and source: if a source was fetched twice on the same day, keep the
    # later run so the dashboard never double counts.
    "counts.csv": """
        SELECT r.run_date, c.source, c.dimension, c.value, c.count
        FROM counts c JOIN runs r USING (run_id)
        WHERE c.run_id = (
            SELECT MAX(c2.run_id) FROM counts c2 JOIN runs r2 USING (run_id)
            WHERE r2.run_date = r.run_date AND c2.source = c.source
        )
        ORDER BY r.run_date, c.source, c.dimension, c.value
    """,
}


def export(conn: sqlite3.Connection, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, sql in QUERIES.items():
        cur = conn.execute(sql)
        path = out_dir / name
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(col[0] for col in cur.description)
            writer.writerows(cur)
        written.append(path)
    return written
