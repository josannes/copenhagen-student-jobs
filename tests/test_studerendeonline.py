from datetime import date

from cphjobs.sources import studerendeonline as so

# Invented listings in the markup StuderendeOnline uses.
CARD = """
<div class="job-item-container">
  <div name="{id}" class="job-item" id="jobItem{id}">
    <div class="clickable job-image">
      <div class="job-logo-square"><img class="lazy" alt="{company} - logo" /></div>
    </div>
    <div class="job-content">
      <a href="/job/{id}/example-slug/example-title/">
        <div class="job-header"> {title} </div>
        <div class="job-teaser">Studiejob, Deltidsjob hos {company}, Storkøbenhavn ( Delvist fjernarbejde ), Øresundsregionen</div>
        <div class="job-description">Ad text we never store.</div>
      </a>
      <div class="info-links">
        <span class="job-date-updated">Opdateret: {updated}</span>
        <span class="job-date-application">Frist: {deadline}</span>
      </div>
    </div>
  </div>
</div>
"""


def list_page(cards, total=414):
    return f"<html><head><title>{total} relevante studiejob, graduate job og praktikpladser</title></head><body>{''.join(cards)}</body></html>"


def card(id, title="Studentermedhjælper til data", company="Eksempel A/S, Afdeling Nord", updated="19.08.2026", deadline="snarest muligt"):
    return CARD.format(id=id, title=title, company=company, updated=updated, deadline=deadline)


def test_parse_list_page():
    postings, total = so.parse_list_page(
        list_page([card(3100001), card(3100002, company="Demo ApS", deadline="30.09.2026"), card(3100003, deadline="løbende")])
    )
    assert total == 414
    first, second, third = postings

    assert first.source_id == "3100001"
    assert first.url == "https://studerendeonline.dk/job/3100001/example-slug/example-title/"
    assert first.title == "Studentermedhjælper til data"
    # A company name with a comma still splits cleanly because the logo alt text gives the name.
    assert first.company == "Eksempel A/S, Afdeling Nord"
    assert first.location == "Storkøbenhavn (Delvist fjernarbejde), Øresundsregionen"
    assert first.listed == date(2026, 8, 19)
    assert (first.deadline, first.deadline_kind) == (None, "asap")

    assert (second.deadline, second.deadline_kind) == (date(2026, 9, 30), "date")
    assert third.deadline_kind == "rolling"
    assert "Ad text" not in repr(postings)


def test_agency_posting_without_logo():
    html = card(3100004, company="Eksempel Rekruttering A/S").replace(" hos ", " via ")
    html = html.replace('<img class="lazy" alt="Eksempel Rekruttering A/S - logo" />', "")
    (posting,), _ = so.parse_list_page(list_page([html]))
    assert posting.company == "Eksempel Rekruttering A/S"
    assert posting.location == "Storkøbenhavn (Delvist fjernarbejde), Øresundsregionen"


def test_parse_sector_counts():
    page = """<p>Vi har opslag fordelt på brancher som
      <a href="/job/?cvtype=4&amt=2&max=20&branche=1">IT &amp; Tele</a> (31 jobopslag),
      <a href="/job/?cvtype=4&amt=2&max=20&branche=2">Kommuner</a> (20 jobopslag) og mere.</p>"""
    assert so.parse_sector_counts(page) == [("IT & Tele", 31), ("Kommuner", 20)]


def test_fetch_pages_until_the_list_ends(monkeypatch):
    monkeypatch.setattr(so, "PAGE_SIZE", 2)
    pages = {
        so.OVERVIEW_URL: "<p></p>",
        so.list_url(1): list_page([card(1), card(2)], total=3),
        so.list_url(2): list_page([card(3)], total=3),
    }

    class FakeClient:
        def __init__(self):
            self.requested = []

        def get(self, url):
            self.requested.append(url)
            return pages[url]

    client = FakeClient()
    result = so.fetch(client)
    assert [p.source_id for p in result.postings] == ["1", "2", "3"]
    assert client.requested == [so.OVERVIEW_URL, so.list_url(1), so.list_url(2)]
    assert [(c.dimension, c.count) for c in result.counts] == [("total", 3)]
