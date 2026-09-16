import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import db
from .enrich import enrich
from .export import export
from .http import PoliteClient
from .site import build as build_site
from .sources import SOURCES

log = logging.getLogger("cphjobs")


def cmd_fetch(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    run_date = datetime.now(ZoneInfo("Europe/Copenhagen")).date()
    run_id = db.start_run(conn, run_date)
    client = PoliteClient(delay=args.delay)

    failed = []
    for name in args.source or SOURCES:
        try:
            result = SOURCES[name](client)
        except Exception:
            log.exception("%s failed, continuing with the other sources", name)
            failed.append(name)
            continue
        db.save(conn, run_id, run_date, result)
        log.info("%s: saved %d postings and %d counts", name, len(result.postings), len(result.counts))

    if args.details:
        try:
            statuses = enrich(conn, client, run_date, limit=args.details_limit)
            log.info("details: %s", dict(statuses) or "nothing new to read")
        except Exception:
            log.exception("details failed, continuing with the export")
            failed.append("details")

    if args.export:
        for path in export(conn, args.export):
            log.info("wrote %s", path)
    return 1 if failed else 0


def cmd_export(args: argparse.Namespace) -> int:
    for path in export(db.connect(args.db), args.out):
        log.info("wrote %s", path)
    return 0


def cmd_site(args: argparse.Namespace) -> int:
    log.info("wrote %s", build_site(db.connect(args.db), args.out))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cphjobs", description="Collect student job postings in Greater Copenhagen."
    )
    parser.add_argument("--db", type=Path, default=Path("data/jobs.db"))
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="collect postings from the portals")
    fetch.add_argument("--source", action="append", choices=list(SOURCES), help="repeatable; default is all")
    fetch.add_argument("--delay", type=float, default=3.0, help="seconds between requests to one site")
    fetch.add_argument("--details", action="store_true", help="also read new postings' own pages")
    fetch.add_argument("--details-limit", type=int, default=200, metavar="N", help="read at most N postings per run")
    fetch.add_argument("--export", type=Path, metavar="DIR", help="also write CSV exports to DIR")
    fetch.set_defaults(func=cmd_fetch)

    exp = sub.add_parser("export", help="write CSV files for the dashboard")
    exp.add_argument("--out", type=Path, default=Path("data/export"))
    exp.set_defaults(func=cmd_export)

    site = sub.add_parser("site", help="build the public dashboard page")
    site.add_argument("--out", type=Path, default=Path("site"))
    site.set_defaults(func=cmd_site)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
