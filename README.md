# Copenhagen Student Jobs

A living picture of the student job market in Greater Copenhagen.

**Dashboard: [josannes.github.io/copenhagen-student-jobs](https://josannes.github.io/copenhagen-student-jobs/)**

> **Status: in progress.** Two portals are collected every day and the dashboard is live.
> More portals and more detail per posting are next.

## What it does

Every morning it collects the student job postings from Danish job portals, keeps the
history in a SQLite database, and publishes a dashboard that answers questions like:

- How many student jobs are open in Greater Copenhagen, and how is that changing?
- Which sectors are hiring students right now?
- When do the deadlines fall, and how many say "apply as soon as possible"?
- Which postings are new, with a link to each one?

The portals only show what is open today. The value here is the history, which grows
every day.

Planned: a map, hours per week, pay where it is stated, and how often Danish is required.
Those need a look at each posting, not just the listing.

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

This writes `data/jobs.db` and two CSV files in `data/export/`. Build the dashboard page
with `uv run cphjobs site`, which writes `site/index.html`. Run the tests with
`uv run pytest`.

A [GitHub Action](.github/workflows/update.yml) runs the collection every day at 07:00
Copenhagen time, commits the updated data to this repository, and publishes the page to
GitHub Pages.

## Data

| Table | One row per | Notes |
|---|---|---|
| `postings` | posting | `first_seen` and `last_seen` are the first and last day it was collected |
| `counts` | run, source and number | Totals the portals report: all postings, hits per search term, postings per sector |
| `runs` | collection run | Date and time |

The CSV exports (`postings.csv`, `counts.csv`) are there for anyone who wants to analyse the
data in Excel, Power BI or elsewhere. They update every day at stable URLs, for example
`https://raw.githubusercontent.com/josannes/copenhagen-student-jobs/main/data/export/postings.csv`.

## Dashboard

One static page, built from the database by [`site.py`](src/cphjobs/site.py). It works
without JavaScript; a small script adds search, filters and hover details. No tracking and
no external scripts.

## Limitations

- Jobindex shows at most 20 results per search, and its robots.txt disallows paging. Jobindex
  postings are therefore a sample, while its hit counts are complete.
- `last_seen` is the last day a posting was collected, not the day it closed.
- The same job can be posted on both portals and then appears twice in the table. The
  headline figures use StuderendeOnline only, so they are not double counted.
- Only portals that can be read without a browser are included for now.

## How it is built

I decide what the tool should do, write the spec, test the results against the portals and
set the priorities. [Claude Code](https://claude.com/claude-code) writes the code.
