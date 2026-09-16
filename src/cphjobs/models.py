from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Posting:
    """One job posting as listed by a portal. Metadata and a link only, never the ad text."""

    source: str
    source_id: str
    title: str
    url: str
    company: str | None = None
    location: str | None = None
    # The date the portal shows on the listing: first published (Jobindex) or last updated
    # (StuderendeOnline).
    listed: date | None = None
    deadline: date | None = None
    # "date", "asap" (apply as soon as possible), "rolling" or None when the portal says nothing.
    deadline_kind: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class Count:
    """A number the portal reports itself, e.g. total hits for a search or postings per sector."""

    source: str
    dimension: str  # "total", "query" or "sector"
    value: str
    count: int


@dataclass
class FetchResult:
    postings: list[Posting] = field(default_factory=list)
    counts: list[Count] = field(default_factory=list)
