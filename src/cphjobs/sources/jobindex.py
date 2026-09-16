"""Jobindex: the 20 most relevant hits per search term in Greater Copenhagen.

We read the regular search page, `/jobsoegning/storkoebenhavn?q=<term>`, which embeds the
results as JSON. The RSS feed Jobindex links to uses `geoareaid=`, and robots.txt disallows
that parameter, as it does paging (`page=`) and any second query parameter. So each term
gives at most 20 postings, plus the total hit count Jobindex reports for it.
"""

import html
import json
import logging
import re
from datetime import date, datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from ..http import PoliteClient
from ..models import Count, FetchResult, Posting

log = logging.getLogger(__name__)

NAME = "jobindex"
BASE = "https://www.jobindex.dk"
AREA = "storkoebenhavn"

# Jobindex searches for any of the words, so multi-word terms are quoted to search for the
# phrase. Each term gets its own request. The last four catch student positions with less
# obvious titles.
QUERIES = [
    "studentermedhjælper",
    "studiejob",
    '"student assistant"',
    '"student worker"',
    "studentermedarbejder",
    '"part-time student"',
    '"student position"',
    '"deltid studerende"',
    "werkstudent",
]

COPENHAGEN = ZoneInfo("Europe/Copenhagen")


def search_url(query: str) -> str:
    return f"{BASE}/jobsoegning/{AREA}?q={quote_plus(query)}"


def _stash(page: str) -> dict:
    marker = "var Stash = "
    start = page.find(marker)
    if start < 0:
        raise ValueError("Jobindex page has no embedded search data")
    data, _ = json.JSONDecoder().raw_decode(page, start + len(marker))
    return data


def _text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(value))).strip() or None


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _in_greater_copenhagen(coords: dict | None) -> bool:
    if not coords or coords.get("latitude") is None or coords.get("longitude") is None:
        return False
    return 55.50 <= coords["latitude"] <= 55.95 and 12.20 <= coords["longitude"] <= 12.70


def _posting(r: dict) -> Posting:
    deadline, kind = None, None
    if r.get("apply_deadline"):
        utc = datetime.fromisoformat(r["apply_deadline"].replace("Z", "+00:00"))
        deadline, kind = utc.astimezone(COPENHAGEN).date(), "date"
    elif r.get("apply_deadline_asap"):
        kind = "asap"

    # Companies with offices across Denmark list all of them. Use the first one in Greater
    # Copenhagen, and leave the coordinates out when none is, so the map stays honest.
    addresses = r.get("addresses") or []
    local = [a for a in addresses if _in_greater_copenhagen(a.get("coordinates"))]
    address = local[0] if local else {"city": (addresses[0] if addresses else {}).get("city")}
    coords = address.get("coordinates") or {}
    company = r.get("companytext") or (r.get("company") or {}).get("name")
    return Posting(
        source=NAME,
        source_id=r["tid"],
        title=_text(r.get("headline")) or "",
        url=r.get("share_url") or f"{BASE}/vis-job/{r['tid']}",
        company=_text(company),
        location=_text(address.get("city") or r.get("area")),
        listed=_date(r.get("firstdate")),
        deadline=deadline,
        deadline_kind=kind,
        latitude=coords.get("latitude"),
        longitude=coords.get("longitude"),
    )


def parse_search_page(page: str) -> tuple[list[Posting], int]:
    response = _stash(page)["jobsearch/result_app"]["storeData"]["searchResponse"]
    return [_posting(r) for r in response["results"]], int(response["hitcount"])


def fetch(client: PoliteClient) -> FetchResult:
    result = FetchResult()
    seen: set[str] = set()
    for query in QUERIES:
        postings, hits = parse_search_page(client.get(search_url(query)))
        result.counts.append(Count(NAME, "query", query, hits))
        new = [p for p in postings if p.source_id not in seen]
        seen.update(p.source_id for p in new)
        result.postings.extend(new)
        log.info("jobindex %r: %d of %d hits, %d new", query, len(postings), hits, len(new))
    return result


def detail_url(posting: dict) -> str | None:
    """Ads with an "h" id are hosted on Jobindex. Others ("r") live on the employer's own
    site, which we don't read."""
    sid = posting["source_id"]
    return f"{BASE}/jobannonce/{sid}/" if sid.startswith("h") else None


def ad_text(page: str) -> str | None:
    body = BeautifulSoup(page, "html.parser").select_one("section.jobtext-jobad__body")
    return re.sub(r"\s+", " ", body.get_text(" ")).strip() or None if body else None
