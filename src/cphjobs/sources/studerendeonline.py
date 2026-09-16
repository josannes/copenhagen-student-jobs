"""StuderendeOnline: every student job in the Capital Region, plus postings per sector.

The public list at `/studiejob/hovedstaden/` pages with JavaScript, but the same search is
available at `/job/?cvtype=4&amt=2` with `max` and `page` in the URL (cvtype 4 is student
jobs, amt 2 is the Capital Region). robots.txt allows `/job/`. The overview page also
reports how many postings the largest sectors have.
"""

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import PoliteClient
from ..models import Count, FetchResult, Posting

log = logging.getLogger(__name__)

NAME = "studerendeonline"
BASE = "https://studerendeonline.dk"
OVERVIEW_URL = f"{BASE}/studiejob/hovedstaden/"
PAGE_SIZE = 100
MAX_PAGES = 15


def list_url(page: int) -> str:
    return f"{BASE}/job/?cvtype=4&amt=2&max={PAGE_SIZE}&page={page}"


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", text))  # "( Delvist fjernarbejde )"


def _dmy(text: str) -> date | None:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    return date(int(m[3]), int(m[2]), int(m[1])) if m else None


def _deadline(text: str) -> tuple[date | None, str | None]:
    text = text.lower()
    if found := _dmy(text):
        return found, "date"
    if "snarest" in text:
        return None, "asap"
    if "løbende" in text:
        return None, "rolling"
    return None, None


def _posting(item) -> Posting | None:
    link = item.select_one(".job-content a[href^='/job/']")
    if link is None:
        return None
    source_id = item.get("name") or re.search(r"/job/(\d+)/", link["href"])[1]

    company = None
    if logo := item.select_one(".job-logo-square img[alt]"):
        company = re.sub(r"\s*-\s*logo$", "", logo["alt"]).strip() or None

    # "Studiejob, Deltidsjob hos <company>, <area>, <area>", or "via <agency>" when a
    # recruitment agency posts on behalf of an unnamed employer.
    location = None
    teaser = item.select_one(".job-teaser")
    text = _clean(teaser.get_text()) if teaser else ""
    if m := re.search(r" (?:hos|via) ", text):
        employer_and_areas = text[m.end() :]
        if company and employer_and_areas.startswith(company):
            location = employer_and_areas[len(company) :].lstrip(", ") or None
        elif company is None:
            company, _, location = (s.strip() for s in employer_and_areas.partition(","))

    updated = item.select_one(".job-date-updated")
    deadline_el = item.select_one(".job-date-application")
    deadline, kind = _deadline(deadline_el.get_text()) if deadline_el else (None, None)
    header = item.select_one(".job-header")
    return Posting(
        source=NAME,
        source_id=str(source_id),
        title=_clean(header.get_text()) if header else _clean(link.get_text()),
        url=BASE + link["href"],
        company=company,
        location=location or None,
        listed=_dmy(updated.get_text()) if updated else None,
        deadline=deadline,
        deadline_kind=kind,
    )


def parse_list_page(page: str) -> tuple[list[Posting], int | None]:
    soup = BeautifulSoup(page, "html.parser")
    postings = [p for item in soup.select("div.job-item") if (p := _posting(item))]
    total = None
    if soup.title and (m := re.match(r"\s*([\d.]+) relevante", soup.title.get_text())):
        total = int(m[1].replace(".", ""))
    return postings, total


def parse_sector_counts(page: str) -> list[tuple[str, int]]:
    soup = BeautifulSoup(page, "html.parser")
    counts = []
    for link in soup.select("a[href*='branche=']"):
        after = link.next_sibling
        if isinstance(after, str) and (m := re.match(r"\s*\((\d+) jobopslag\)", after)):
            counts.append((_clean(link.get_text()), int(m[1])))
    return counts


def fetch(client: PoliteClient) -> FetchResult:
    result = FetchResult()
    for sector, n in parse_sector_counts(client.get(OVERVIEW_URL)):
        result.counts.append(Count(NAME, "sector", sector, n))

    seen: set[str] = set()
    total = None
    for page_no in range(1, MAX_PAGES + 1):
        postings, page_total = parse_list_page(client.get(list_url(page_no)))
        total = total or page_total
        new = [p for p in postings if p.source_id not in seen]
        seen.update(p.source_id for p in new)
        result.postings.extend(new)
        log.info("studerendeonline page %d: %d postings, %d new", page_no, len(postings), len(new))
        if len(postings) < PAGE_SIZE or not new or (total and len(seen) >= total):
            break
    else:
        log.warning("studerendeonline: stopped after %d pages, the list may be longer", MAX_PAGES)

    if total is not None:
        result.counts.append(Count(NAME, "total", "all", total))
    return result
