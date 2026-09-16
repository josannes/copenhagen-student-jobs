import json
from datetime import date

from cphjobs.sources import jobindex

# Invented postings in the shape Jobindex embeds in its search page.
RESULTS = [
    {
        "tid": "h1000001",
        "headline": "Student Assistant for &lt;b&gt;Data&lt;/b&gt; Team",
        "companytext": "Example Analytics ApS",
        "addresses": [{"city": "København K", "coordinates": {"latitude": 55.68, "longitude": 12.57}}],
        "area": "København K",
        "firstdate": "2026-09-01",
        "apply_deadline": "2026-09-30T21:59:59Z",
        "apply_deadline_asap": False,
        "share_url": "https://www.jobindex.dk/vis-job/h1000001",
        "html": "<p>The full ad text, which we never store.</p>",
    },
    {
        "tid": "r2000002",
        "headline": "Studentermedhjælper",
        "companytext": None,
        "company": {"name": "Eksempel Kommune"},
        "addresses": [],
        "area": "Frederiksberg",
        "firstdate": "2026-09-10",
        "apply_deadline": None,
        "apply_deadline_asap": True,
        "share_url": None,
    },
]


def page(results=RESULTS, hitcount=141):
    stash = {"jobsearch/result_app": {"storeData": {"searchResponse": {"hitcount": hitcount, "results": results}}}}
    return f"<html><script>var Stash = {json.dumps(stash)};</script></html>"


def test_parse_search_page():
    postings, hits = jobindex.parse_search_page(page())
    assert hits == 141
    first, second = postings

    assert first.source_id == "h1000001"
    assert first.title == "Student Assistant for Data Team"
    assert first.company == "Example Analytics ApS"
    assert first.location == "København K"
    assert (first.latitude, first.longitude) == (55.68, 12.57)
    assert first.listed == date(2026, 9, 1)
    # 21:59:59 UTC is 23:59:59 in Copenhagen during summer time, so still the 30th.
    assert (first.deadline, first.deadline_kind) == (date(2026, 9, 30), "date")

    assert second.company == "Eksempel Kommune"
    assert second.location == "Frederiksberg"
    assert (second.deadline, second.deadline_kind) == (None, "asap")
    assert second.url == "https://www.jobindex.dk/vis-job/r2000002"


def test_picks_the_address_in_greater_copenhagen():
    offices = [
        {"city": "Aarhus C", "coordinates": {"latitude": 56.15, "longitude": 10.20}},
        {"city": "Frederiksberg", "coordinates": {"latitude": 55.68, "longitude": 12.53}},
    ]
    elsewhere = [{"city": "Odense C", "coordinates": {"latitude": 55.40, "longitude": 10.39}}]
    (local,), _ = jobindex.parse_search_page(page([RESULTS[0] | {"addresses": offices}]))
    (remote,), _ = jobindex.parse_search_page(page([RESULTS[0] | {"addresses": elsewhere}]))

    assert (local.location, local.latitude) == ("Frederiksberg", 55.68)
    assert (remote.location, remote.latitude) == ("Odense C", None)


def test_ad_text_is_not_kept():
    postings, _ = jobindex.parse_search_page(page())
    assert "full ad text" not in repr(postings)


def test_search_url_has_a_single_parameter():
    assert jobindex.search_url("student assistant") == (
        "https://www.jobindex.dk/jobsoegning/storkoebenhavn?q=student+assistant"
    )


def test_fetch_deduplicates_across_queries():
    class FakeClient:
        def get(self, url):
            return page()

    result = jobindex.fetch(FakeClient())
    assert len(result.postings) == 2
    assert len(result.counts) == len(jobindex.QUERIES)
