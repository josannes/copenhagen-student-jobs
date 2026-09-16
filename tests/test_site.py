from datetime import date

from cphjobs import db
from cphjobs.models import Count, FetchResult, Posting
from cphjobs.site import build, load, render


def run(conn, day, postings, counts):
    db.save(conn, db.start_run(conn, day), day, FetchResult(postings, counts))


def so(id, **changes):
    base = dict(source="studerendeonline", source_id=id, title=f"Job {id}", url=f"https://example.org/{id}")
    return Posting(**(base | changes))


def test_page_from_one_run(tmp_path):
    conn = db.connect(":memory:")
    day = date(2026, 9, 15)
    run(
        conn,
        day,
        [
            so("1", deadline_kind="asap", listed=date(2026, 9, 14)),
            so("2", deadline=date(2026, 9, 20), deadline_kind="date"),
            so("3", deadline=date(2026, 9, 1), deadline_kind="date"),  # already passed
        ],
        [Count("studerendeonline", "total", "all", 414), Count("studerendeonline", "sector", "IT & Tele", 31)],
    )
    page = (build(conn, tmp_path)).read_text()

    assert "414" in page
    assert "IT &amp; Tele" in page
    assert "The history starts on 15 Sep 2026" in page
    assert "Job 1" in page and "Job 2" in page
    assert "Job 3" not in page  # deadline passed
    assert "50%" in page  # one of two open postings says as soon as possible


def test_line_appears_with_two_days():
    conn = db.connect(":memory:")
    for day, total in ((date(2026, 9, 15), 414), (date(2026, 9, 16), 420)):
        run(conn, day, [so("1")], [Count("studerendeonline", "total", "all", total)])
    page = render(load(conn))
    assert '<svg class="line-chart"' in page
    assert ">420</text>" in page


def test_portal_text_is_escaped_and_links_are_safe():
    conn = db.connect(":memory:")
    day = date(2026, 9, 15)
    evil = so("1", title='<script>alert(1)</script> {{repo}}', url="javascript:alert(1)")
    run(conn, day, [evil], [Count("studerendeonline", "total", "all", 1)])
    page = render(load(conn))
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; {{repo}}" in page
    assert 'href="javascript:' not in page


def test_requirement_tiles_and_language_filter():
    conn = db.connect(":memory:")
    day = date(2026, 9, 16)
    run(conn, day, [so("1"), so("2"), so("3"), so("4")], [Count("studerendeonline", "total", "all", 4)])
    rows = [
        ("1", "ok", "en", "optional", 15, 20),
        ("2", "ok", "da", "required", 10, 10),
        ("3", "gone", None, None, None, None),
        ("4", "external", None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO details (source, source_id, checked_on, status, language, danish, hours_min, hours_max)"
        " VALUES ('studerendeonline', ?, '2026-09-16', ?, ?, ?, ?, ?)",
        rows,
    )
    page = render(load(conn))
    assert "Job 3" not in page  # removed from the portal
    assert "Written in English" in page and "50%" in page
    assert "English, Danish optional" in page
    assert 'data-no-danish="1"' in page
    assert ">15-20<" in page
    assert "Details on employer&#x27;s site" in page or "Details on employer's site" in page
