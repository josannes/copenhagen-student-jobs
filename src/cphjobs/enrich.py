"""Read each open posting's own page once and store what `details.extract` finds."""

import logging
import sqlite3
import urllib.error
from collections import Counter
from dataclasses import asdict
from datetime import date

from .details import extract
from .http import DisallowedByRobots, ExternalRedirect, PoliteClient
from .sources import MODULES

log = logging.getLogger(__name__)

# Open postings (seen on their source's latest run) that haven't been read, plus earlier
# errors from a previous day. Newest first, so a limited run covers what students see first.
PENDING = """
SELECT p.source, p.source_id, p.url
FROM postings p LEFT JOIN details d USING (source, source_id)
WHERE p.last_seen = (SELECT MAX(last_seen) FROM postings WHERE source = p.source)
  AND (d.source_id IS NULL OR (d.status = 'error' AND d.checked_on < :today))
ORDER BY p.first_seen DESC, p.listed DESC
LIMIT :limit
"""

SAVE = """
INSERT OR REPLACE INTO details
    (source, source_id, checked_on, status, language, danish, hours_min, hours_max, pay_min, pay_max, pay_kind)
VALUES
    (:source, :source_id, :checked_on, :status, :language, :danish, :hours_min, :hours_max, :pay_min, :pay_max, :pay_kind)
"""

EMPTY = dict.fromkeys(("language", "danish", "hours_min", "hours_max", "pay_min", "pay_max", "pay_kind"))


def read_posting(client: PoliteClient, posting: dict) -> dict:
    module = MODULES[posting["source"]]
    url = module.detail_url(posting)
    if url is None:
        return {"status": "external"}
    try:
        text = module.ad_text(client.get(url))
    except ExternalRedirect:
        return {"status": "external"}
    except DisallowedByRobots:
        return {"status": "disallowed"}
    except urllib.error.HTTPError as e:
        return {"status": "gone" if e.code in (404, 410) else "error"}
    except (urllib.error.URLError, TimeoutError) as e:
        log.warning("could not read %s: %s", url, e)
        return {"status": "error"}
    if not text:
        return {"status": "no_text"}
    return {"status": "ok"} | asdict(extract(text))


def enrich(conn: sqlite3.Connection, client: PoliteClient, today: date, limit: int = 200) -> Counter:
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(PENDING, {"today": today.isoformat(), "limit": limit})]
    statuses = Counter()
    for i, posting in enumerate(rows, 1):
        result = EMPTY | read_posting(client, posting)
        with conn:
            conn.execute(SAVE, result | {"source": posting["source"], "source_id": posting["source_id"], "checked_on": today.isoformat()})
        statuses[result["status"]] += 1
        if i % 50 == 0:
            log.info("details: read %d of %d", i, len(rows))
    conn.row_factory = None
    return statuses
