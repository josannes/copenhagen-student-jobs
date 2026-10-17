"""Decide which open postings the dashboard shows, and count the same job once.

The database keeps everything the portals list. This only shapes the public view: postings
nobody has updated in months, jobs in other cities and things that aren't student jobs are
left out, and a job listed twice (on both portals, or twice on one) becomes one row.
"""

import re
from collections import Counter
from datetime import date, timedelta

# StuderendeOnline's date is when the posting was last updated. Some stay up for years.
STALE_AFTER = timedelta(days=90)

# Postings in the Capital Region on StuderendeOnline can also be tagged with other regions,
# e.g. a university with campuses in Copenhagen and Aalborg. A title that names a city
# outside the area, and not Copenhagen, is taken to be a job there.
OTHER_CITY = re.compile(
    r"\b(aalborg|aarhus|århus|odense|kolding|vejle|horsens|randers|herning|holstebro|"
    r"silkeborg|viborg|esbjerg|fredericia|sønderborg|aabenraa|haderslev|svendborg|"
    r"slagelse|næstved|holbæk|kalundborg|ringsted|sorø|nykøbing|nakskov|rønne)\b",
    re.IGNORECASE,
)
COPENHAGEN = re.compile(r"københavn|copenhagen|\bkbh\b|\bcph\b|frederiksberg", re.IGNORECASE)
# University names don't say where the job is.
UNIVERSITY_NAMES = re.compile(r"aalborg universitet|aarhus universitet|aalborg university|aarhus university", re.IGNORECASE)

# PhD positions and recruitment events turn up in searches for student jobs.
NOT_A_JOB = re.compile(
    r"\bph\.?\s?d\b|\ban evening for\b|\binformation (?:meeting|evening)\b|\binfomøde\b|\bwebinar\b",
    re.IGNORECASE,
)

REASONS = {
    "stale": "not updated in the last 90 days",
    "elsewhere": "in a city outside Greater Copenhagen",
    "not_a_job": "PhD positions or events, not student jobs",
}


def hidden_reason(p: dict, as_of: date) -> str | None:
    if p["listed"] and date.fromisoformat(p["listed"]) < as_of - STALE_AFTER:
        return "stale"
    title = p["title"]
    if OTHER_CITY.search(UNIVERSITY_NAMES.sub("", title)) and not COPENHAGEN.search(title):
        return "elsewhere"
    if NOT_A_JOB.search(title):
        return "not_a_job"
    return None


def _words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9æøå]+", text.lower()))


def _company(name: str | None) -> str:
    words = _words(name or "").split()
    return " ".join(w for w in words if w not in {"a", "s", "aps", "as", "amba"})


def _key(p: dict) -> tuple:
    title = _words(p["title"])
    # A long title is specific enough on its own. The portals spell company names
    # differently ("DTU" and "Danmarks Tekniske Universitet"), so they aren't compared.
    if len(title.split()) >= 5:
        return (title,)
    # "Student Assistant" is not: also require the same company and deadline.
    return (title, _company(p["company"]), p["deadline"])


# Prefer this portal's copy of a job: it lists every student job and its postings are read
# for language and hours.
PREFERRED_SOURCE = "studerendeonline"


def _rank(p: dict) -> tuple:
    return (p["source"] == PREFERRED_SOURCE, p["details_status"] == "ok", p["listed"] or "")


def merge(postings: list[dict]) -> list[dict]:
    """One row per job. The kept row gets `also`: the other portals' copies, as (source, url)."""
    groups: dict[tuple, list[dict]] = {}
    for p in postings:
        groups.setdefault(_key(p), []).append(p)
    merged = []
    for group in groups.values():
        group.sort(key=_rank, reverse=True)
        keep = dict(group[0])
        others = [p for p in group[1:] if p["source"] != keep["source"]]
        keep["also"] = sorted({(p["source"], p["url"]) for p in others})
        if not keep["deadline"]:
            # One portal may give a date where the other just says "as soon as possible".
            if dated := [p for p in group if p["deadline"]]:
                keep["deadline"], keep["deadline_kind"] = dated[0]["deadline"], dated[0]["deadline_kind"]
        merged.append(keep)
    return merged


def clean(postings: list[dict], as_of: date) -> tuple[list[dict], Counter]:
    """The postings to show, and how many were left out for each reason."""
    hidden: Counter = Counter()
    shown = []
    for p in postings:
        if reason := hidden_reason(p, as_of):
            hidden[reason] += 1
        else:
            shown.append(p)
    merged = merge(shown)
    hidden["duplicate"] = len(shown) - len(merged)
    return merged, hidden
