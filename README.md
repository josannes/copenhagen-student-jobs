# Copenhagen Student Jobs

A living picture of the student job market in Greater Copenhagen.

> **Status: in progress.** Collection from two portals works. The dashboard and the
> scheduled updates are being built.

## What it does

It collects student job postings from Danish job portals, keeps the history in a SQLite
database, and turns it into a dashboard that answers questions like:

- Which sectors are hiring students right now, and how is that changing week by week?
- How many student jobs are open in Greater Copenhagen?
- Where in the city are they?
- When do the deadlines fall, and how many say "apply as soon as possible"?

Planned: hours per week, pay where it is stated, and how often Danish is required. Those
need a look at each posting, not just the listing.

## Who it is for

Students in Copenhagen looking for a student job, especially international students who
are new to the Danish job market. Also study advisers and career centres who would like
numbers instead of impressions.

## Why I built it

I'm a student in Copenhagen, and in autumn 2026 I was looking for a student job myself. I
was already going through the same portals every week, and the postings I collected
answer questions every international student here has: which sectors hire students, how
many hours, whether Danish is required, and when to apply.

## Sources

| Portal | What is read | Coverage |
|---|---|---|
| [Jobindex](https://www.jobindex.dk) | The search page for Greater Copenhagen, one request per search term (9 terms) | The 20 most relevant postings per term, plus the total number of hits per term |
| [StuderendeOnline](https://studerendeonline.dk) | All student jobs in the Capital Region, 100 per page | Every posting, plus the number of postings in the largest sectors |

More portals will be added where their terms and robots.txt allow it.

## How it collects, and what it keeps

- **robots.txt is checked before every request**, with support for the `*` wildcards the
  portals use, and anything it disallows is refused. That is why the Jobindex RSS feed is
  not used: robots.txt disallows its `geoareaid` parameter.
- One request every three seconds per site, with a user agent that links to this repository.
- **Kept:** title, company, location, link, the listing date and the deadline.
  **Not kept:** the ad text, contact persons or any other personal data. To read a
  posting, follow the link to the portal.

## Run it yourself

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run cphjobs fetch --export data/export
```

This writes `data/jobs.db` and two CSV files in `data/export/`. Run the tests with
`uv run pytest`.

## Data

| Table | One row per | Notes |
|---|---|---|
| `postings` | posting | `first_seen` and `last_seen` are the first and last day it was collected |
| `counts` | run, source and number | Totals the portals report: all postings, hits per search term, postings per sector |
| `runs` | collection run | Date and time |

The CSV exports (`postings.csv`, `counts.csv`) are what the dashboard reads.

## Dashboard

Built in Power BI on top of the CSV exports, so the published report refreshes on its own.
Link coming.

## Limitations

- Jobindex shows at most 20 results per search, and its robots.txt disallows paging. Jobindex
  postings are therefore a sample, while its hit counts are complete.
- `last_seen` is the last day a posting was collected, not the day it closed.
- Only portals that can be read without a browser are included for now.

## How it is built

I decide what the tool should do, write the spec, test the results against the portals and
set the priorities. [Claude Code](https://claude.com/claude-code) writes the code.
