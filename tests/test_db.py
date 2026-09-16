import csv
from datetime import date

from cphjobs import db
from cphjobs.export import export
from cphjobs.models import Count, FetchResult, Posting


def posting(**changes):
    base = dict(source="jobindex", source_id="h1", title="Student Assistant", url="https://example.org/h1")
    return Posting(**(base | changes))


def test_first_seen_stays_and_last_seen_moves():
    conn = db.connect(":memory:")
    day1, day2 = date(2026, 9, 14), date(2026, 9, 21)

    db.save(conn, db.start_run(conn, day1), day1, FetchResult([posting()]))
    db.save(conn, db.start_run(conn, day2), day2, FetchResult([posting(title="Student Assistant, Data")]))

    rows = conn.execute("SELECT title, first_seen, last_seen FROM postings").fetchall()
    assert rows == [("Student Assistant, Data", "2026-09-14", "2026-09-21")]


def test_export_keeps_the_last_run_of_a_day(tmp_path):
    conn = db.connect(":memory:")
    day = date(2026, 9, 15)
    for hits in (100, 141):
        run = db.start_run(conn, day)
        db.save(conn, run, day, FetchResult([posting()], [Count("jobindex", "query", "studiejob", hits)]))

    export(conn, tmp_path)
    with (tmp_path / "counts.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert rows == [
        {"run_date": "2026-09-15", "source": "jobindex", "dimension": "query", "value": "studiejob", "count": "141"}
    ]
    assert (tmp_path / "postings.csv").exists()
