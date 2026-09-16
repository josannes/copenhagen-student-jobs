import urllib.error
from datetime import date

import pytest

from cphjobs import db
from cphjobs.enrich import enrich
from cphjobs.http import DisallowedByRobots, ExternalRedirect, PoliteClient, _GuardedRedirects
from cphjobs.models import FetchResult, Posting

TODAY = date(2026, 9, 16)

AD = """<html><div class="jobContent"><p>We are looking for a student assistant to join our team in Copenhagen.
You are fluent in English and Danish is an advantage. The job is 15-20 hours per week and the hourly wage
is DKK 160. You will work with our data and you can grow with us.</p></div></html>"""


def so(id):
    return Posting("studerendeonline", id, f"Job {id}", f"https://studerendeonline.dk/job/{id}/x/y/")


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def http_error(code):
    return urllib.error.HTTPError("https://x", code, "error", {}, None)


def test_reads_each_open_posting_once():
    conn = db.connect(":memory:")
    postings = [so("1"), so("2"), so("3"), so("4"), Posting("jobindex", "r99", "External", "https://www.jobindex.dk/vis-job/r99")]
    db.save(conn, db.start_run(conn, TODAY), TODAY, FetchResult(postings))
    client = FakeClient({
        so("1").url: AD,
        so("2").url: http_error(410),
        so("3").url: "<html>no ad text here</html>",
        so("4").url: ExternalRedirect("https://employer.example/jobs/4"),
    })

    statuses = enrich(conn, client, TODAY)
    assert statuses == {"ok": 1, "gone": 1, "no_text": 1, "external": 2}
    assert "https://www.jobindex.dk/vis-job/r99" not in client.requested  # employer sites are never requested

    row = conn.execute("SELECT language, danish, hours_min, hours_max, pay_min, pay_kind FROM details WHERE source_id = '1'").fetchone()
    assert row == ("en", "optional", 15, 20, 160, "stated")

    assert enrich(conn, client, TODAY) == {}  # nothing is read twice
    assert len(client.requested) == 4


def test_errors_are_retried_on_a_later_day():
    conn = db.connect(":memory:")
    db.save(conn, db.start_run(conn, TODAY), TODAY, FetchResult([so("1")]))
    assert enrich(conn, FakeClient({so("1").url: http_error(503)}), TODAY) == {"error": 1}
    assert enrich(conn, FakeClient({so("1").url: AD}), TODAY) == {}
    assert enrich(conn, FakeClient({so("1").url: AD}), date(2026, 9, 17)) == {"ok": 1}


class FakeRequest:
    full_url = "https://studerendeonline.dk/job/1/"


def test_redirects_to_other_sites_are_refused():
    guard = _GuardedRedirects(PoliteClient())
    with pytest.raises(ExternalRedirect):
        guard.redirect_request(FakeRequest(), None, 302, "Found", {}, "https://jobs.employer.example/1")


def test_redirects_on_the_same_site_obey_robots():
    client = PoliteClient()
    client.allowed = lambda url: not url.endswith("/private/")
    guard = _GuardedRedirects(client)
    with pytest.raises(DisallowedByRobots):
        guard.redirect_request(FakeRequest(), None, 302, "Found", {}, "https://studerendeonline.dk/private/")
