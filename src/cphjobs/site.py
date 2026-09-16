"""Build the public dashboard: one static HTML page, rendered from the database.

Everything is rendered here in Python, so the page works without JavaScript. The small
script at the bottom only adds search, filters and hover details.
"""

import html
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REPO_URL = "https://github.com/josannes/copenhagen-student-jobs"
COMPLETE_SOURCE = "studerendeonline"  # lists every student job, so the headline figures use it
SOURCE_NAMES = {"jobindex": "Jobindex", "studerendeonline": "StuderendeOnline"}


@dataclass
class Dashboard:
    as_of: date
    total_series: list[tuple[date, int]]
    sectors: list[tuple[str, int]]
    postings: list[dict]

    @property
    def complete(self) -> list[dict]:
        return [p for p in self.postings if p["source"] == COMPLETE_SOURCE]


def load(conn: sqlite3.Connection) -> Dashboard | None:
    conn.row_factory = sqlite3.Row
    latest = conn.execute("SELECT MAX(run_date) FROM runs").fetchone()[0]
    if latest is None:
        return None
    as_of = date.fromisoformat(latest)

    total_series = [
        (date.fromisoformat(r["run_date"]), r["count"])
        for r in conn.execute(
            """
            SELECT r.run_date, c.count
            FROM counts c JOIN runs r USING (run_id)
            WHERE c.source = ? AND c.dimension = 'total'
              AND c.run_id = (
                  SELECT MAX(c2.run_id) FROM counts c2 JOIN runs r2 USING (run_id)
                  WHERE r2.run_date = r.run_date AND c2.source = c.source
                    AND c2.dimension = 'total')
            ORDER BY r.run_date
            """,
            (COMPLETE_SOURCE,),
        )
    ]
    sectors = [
        (r["value"], r["count"])
        for r in conn.execute(
            """
            SELECT value, count FROM counts
            WHERE source = ? AND dimension = 'sector'
              AND run_id = (SELECT MAX(run_id) FROM counts WHERE source = ? AND dimension = 'sector')
            ORDER BY count DESC, value
            """,
            (COMPLETE_SOURCE, COMPLETE_SOURCE),
        )
    ]
    # Open = collected on the source's latest run, and the deadline hasn't passed.
    postings = [
        dict(r)
        for r in conn.execute(
            """
            SELECT * FROM postings p
            WHERE last_seen = (SELECT MAX(last_seen) FROM postings WHERE source = p.source)
              AND (deadline IS NULL OR deadline >= ?)
            ORDER BY listed DESC, title
            """,
            (latest,),
        )
    ]
    return Dashboard(as_of, total_series, sectors, postings)


# ---------------------------------------------------------------- formatting

e = html.escape


def fmt_date(d: date | str | None) -> str:
    if not d:
        return ""
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d.day} {d:%b %Y}"


def fmt_int(n: int) -> str:
    return f"{n:,}"


def safe_url(url: str) -> str:
    return url if url.startswith(("https://", "http://")) else "#"


def deadline_text(p: dict) -> str:
    if p["deadline"]:
        return fmt_date(p["deadline"])
    return {"asap": "As soon as possible", "rolling": "Rolling"}.get(p["deadline_kind"], "Not stated")


# ---------------------------------------------------------------- sections


def stat_tiles(d: Dashboard) -> str:
    postings = d.complete
    week = d.as_of + timedelta(days=7)
    asap = sum(p["deadline_kind"] == "asap" for p in postings)
    due = sum(bool(p["deadline"]) and p["deadline"] <= week.isoformat() for p in postings)
    recent = sum(bool(p["listed"]) and p["listed"] > (d.as_of - timedelta(days=7)).isoformat() for p in postings)
    share = round(100 * asap / len(postings)) if postings else 0
    tiles = [
        ("No fixed deadline", f"{share}%", f"{fmt_int(asap)} postings say apply as soon as possible"),
        ("Deadline within 7 days", fmt_int(due), f"by {fmt_date(week)}"),
        ("Posted or updated in the last 7 days", fmt_int(recent), "a rough measure of new postings"),
    ]
    return "".join(
        f'<div class="tile"><div class="tile-label">{e(label)}</div>'
        f'<div class="tile-value">{e(value)}</div><div class="tile-note">{e(note)}</div></div>'
        for label, value, note in tiles
    )


def sector_bars(d: Dashboard) -> str:
    if not d.sectors:
        return '<p class="empty">No sector figures yet.</p>'
    top = max(n for _, n in d.sectors)
    total = d.total_series[-1][1] if d.total_series else None
    rows = []
    for name, n in d.sectors:
        share = f" · {round(100 * n / total)}% of all postings" if total else ""
        rows.append(
            f'<div class="bar-row" tabindex="0" data-tip-value="{fmt_int(n)} postings" data-tip-label="{e(name)}{share}">'
            f'<span class="bar-label">{e(name)}</span>'
            f'<span class="bar-track"><span class="bar" style="width:{100 * n / top:.1f}%"></span>'
            f'<span class="bar-value">{fmt_int(n)}</span></span></div>'
        )
    return "".join(rows)


def nice_max(value: int) -> int:
    for step in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000):
        if value <= step * 5:
            return max(step, -(-value // step) * step)
    return value


def total_line(d: Dashboard) -> str:
    series = d.total_series
    if len(series) < 2:
        start = fmt_date(series[0][0]) if series else "the first update"
        return (
            f'<p class="empty">The history starts on {e(start)}. '
            "The line appears after the next update and grows every day.</p>"
        )

    w, h, left, right, top, bottom = 420, 220, 40, 44, 12, 26
    ymax = nice_max(max(n for _, n in series))
    x0, x1 = series[0][0], series[-1][0]
    span = max((x1 - x0).days, 1)

    def x(day: date) -> float:
        return left + (w - left - right) * (day - x0).days / span

    def y(n: int) -> float:
        return top + (h - top - bottom) * (1 - n / ymax)

    grid = "".join(
        f'<line class="grid" x1="{left}" x2="{w - right}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        f'<text class="tick" x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{fmt_int(v)}</text>'
        for v in (0, ymax // 2, ymax)
    )
    points = " ".join(f"{x(day):.1f},{y(n):.1f}" for day, n in series)
    last_day, last_n = series[-1]
    data = json.dumps([[fmt_date(day), n, round(x(day), 1)] for day, n in series])
    return (
        f'<svg class="line-chart" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="Open student jobs per day, from {fmt_int(series[0][1])} to {fmt_int(last_n)}" '
        f"data-points='{e(data)}' data-top=\"{top}\" data-bottom=\"{h - bottom}\">"
        f"{grid}"
        f'<text class="tick" x="{left}" y="{h - 8}">{e(fmt_date(x0))}</text>'
        f'<text class="tick" x="{w - right}" y="{h - 8}" text-anchor="end">{e(fmt_date(x1))}</text>'
        f'<polyline class="line" points="{points}"/>'
        f'<circle class="dot" cx="{x(last_day):.1f}" cy="{y(last_n):.1f}" r="4"/>'
        f'<text class="end-label" x="{x(last_day) + 10:.1f}" y="{y(last_n) + 4:.1f}">{fmt_int(last_n)}</text>'
        f'<line class="crosshair" y1="{top}" y2="{h - bottom}" x1="0" x2="0" visibility="hidden"/>'
        f'<rect class="hit" x="{left}" y="0" width="{w - left - right}" height="{h}"/>'
        "</svg>"
    )


def posting_rows(d: Dashboard) -> str:
    rows = []
    for p in d.postings:
        source = SOURCE_NAMES.get(p["source"], p["source"])
        haystack = " ".join(filter(None, (p["title"], p["company"], p["location"]))).lower()
        rows.append(
            f'<tr data-source="{e(p["source"])}" data-deadline="{e(p["deadline"] or "")}" '
            f'data-listed="{e(p["listed"] or "")}" data-search="{e(haystack)}">'
            f'<td class="col-title"><a href="{e(safe_url(p["url"]))}" rel="noopener">{e(p["title"])}</a></td>'
            f'<td data-label="Company">{e(p["company"] or "")}</td>'
            f'<td data-label="Location">{e(p["location"] or "")}</td>'
            f'<td data-label="Deadline">{e(deadline_text(p))}</td>'
            f'<td data-label="Listed" class="num">{e(fmt_date(p["listed"]))}</td>'
            f'<td data-label="Source">{e(source)}</td></tr>'
        )
    return "".join(rows)


# ---------------------------------------------------------------- page


def render(d: Dashboard) -> str:
    total = d.total_series[-1][1] if d.total_series else len(d.complete)
    sector_sum = sum(n for _, n in d.sectors)
    counts_by_source = {s: sum(p["source"] == s for p in d.postings) for s in SOURCE_NAMES}
    source_options = "".join(
        f'<option value="{s}">{e(name)} ({fmt_int(counts_by_source[s])})</option>'
        for s, name in SOURCE_NAMES.items()
    )
    values = {
        "as_of": e(fmt_date(d.as_of)),
        "total": fmt_int(total),
        "tiles": stat_tiles(d),
        "sector_note": e(f"The largest sectors on StuderendeOnline, {fmt_int(sector_sum)} of {fmt_int(total)} postings."),
        "sector_bars": sector_bars(d),
        "total_line": total_line(d),
        "source_options": source_options,
        "posting_count": fmt_int(len(d.postings)),
        "rows": posting_rows(d),
        "repo": REPO_URL,
    }
    # One pass, so text from the portals can never be mistaken for a placeholder.
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m[1]], TEMPLATE)


def build(conn: sqlite3.Connection, out_dir: Path) -> Path:
    dashboard = load(conn)
    if dashboard is None:
        raise SystemExit("The database has no runs yet. Run `cphjobs fetch` first.")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render(dashboard), encoding="utf-8")
    return path


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Student jobs in Greater Copenhagen</title>
<meta name="description" content="How many student jobs are open in Greater Copenhagen, which sectors are hiring, and when the deadlines fall. Updated every day.">
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #6b6a65;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10); --series: #2a78d6;
  --series-soft: rgba(42,120,214,0.10); --link: #1c5cab; --hover: rgba(11,11,11,0.04);
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #9a9890;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --series: #3987e5;
    --series-soft: rgba(57,135,229,0.12); --link: #86b6ef; --hover: rgba(255,255,255,0.05);
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1040px; margin: 0 auto; padding-inline: 16px; padding-block: 32px 48px; }
a { color: var(--link); }
header p, .note, .empty, footer { color: var(--ink-2); }
h1 { font-size: 1.75rem; line-height: 1.2; margin: 0 0 4px; }
h2 { font-size: 1.1rem; margin: 0 0 4px; }
.meta { margin: 0; font-size: 0.9rem; }
.hero { margin: 28px 0 20px; }
.hero-value { font-size: 64px; font-weight: 600; line-height: 1; }
.hero-label { font-size: 1.05rem; color: var(--ink-2); margin-top: 6px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.card, .tile { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
.tile { padding: 16px; }
.tile-label { font-size: 0.9rem; color: var(--ink-2); }
.tile-value { font-size: 2rem; font-weight: 600; line-height: 1.2; margin: 4px 0; }
.tile-note { font-size: 0.85rem; color: var(--muted); }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; margin-top: 12px; }
.card { padding: 20px; min-width: 0; }
.note { font-size: 0.9rem; margin: 0 0 16px; }
.bar-row { display: grid; grid-template-columns: minmax(0, 11rem) 1fr; gap: 12px; align-items: center;
  padding: 3px 0; border-radius: 6px; outline: none; }
.bar-row:hover, .bar-row:focus-visible { background: var(--hover); }
.bar-label { font-size: 0.85rem; color: var(--ink-2); overflow-wrap: anywhere; }
.bar-track { display: flex; align-items: center; gap: 8px; min-width: 0; }
.bar { display: block; height: 18px; background: var(--series); border-radius: 0 4px 4px 0; min-width: 2px; }
.bar-value { font-size: 0.85rem; font-variant-numeric: tabular-nums; flex: none; }
.line-chart { width: 100%; height: auto; display: block; overflow: visible; }
.line-chart .grid { stroke: var(--grid); stroke-width: 1; }
.line-chart .tick { fill: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.line-chart .line { fill: none; stroke: var(--series); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.line-chart .dot { fill: var(--series); stroke: var(--surface); stroke-width: 2; }
.line-chart .end-label { fill: var(--ink); font-size: 14px; font-weight: 600; }
.line-chart .crosshair { stroke: var(--axis); stroke-width: 1; }
.line-chart .hit { fill: transparent; }
.tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink);
  border: 1px solid var(--border); border-radius: 8px; padding: 6px 10px; font-size: 0.85rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12); z-index: 10; max-width: 260px; }
.tip strong { display: block; font-size: 1rem; }
.tip span { color: var(--ink-2); }
section.postings { margin-top: 12px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.filters input, .filters select { font: inherit; color: var(--ink); background: var(--page);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
.filters input { flex: 1 1 240px; min-width: 0; }
.count { color: var(--muted); font-size: 0.9rem; margin: 0 0 8px; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th { text-align: left; font-weight: 600; color: var(--ink-2); border-bottom: 1px solid var(--axis); padding: 8px; }
td { border-bottom: 1px solid var(--grid); padding: 8px; vertical-align: top; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.col-title a { font-weight: 500; }
@media (max-width: 860px) {
  .hero-value { font-size: 48px; }
  thead { display: none; }
  table, tbody, tr, td { display: block; }
  tr { padding: 10px 0; border-bottom: 1px solid var(--grid); }
  td { border: 0; padding: 2px 0; }
  td[data-label]::before { content: attr(data-label) ": "; color: var(--muted); }
  td:empty { display: none; }
}
footer { margin-top: 32px; font-size: 0.9rem; }
footer p { margin: 6px 0; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Student jobs in Greater Copenhagen</h1>
  <p class="meta">Updated {{as_of}} from Jobindex and StuderendeOnline. <a href="#about">How this works</a></p>
</header>

<div class="hero">
  <div class="hero-value">{{total}}</div>
  <div class="hero-label">student jobs open in the Capital Region on StuderendeOnline</div>
</div>

<div class="tiles">{{tiles}}</div>

<div class="grid-2">
  <section class="card">
    <h2>Which sectors are hiring</h2>
    <p class="note">{{sector_note}}</p>
    {{sector_bars}}
  </section>
  <section class="card">
    <h2>Open student jobs over time</h2>
    <p class="note">All student jobs in the Capital Region on StuderendeOnline, per day.</p>
    {{total_line}}
  </section>
</div>

<section class="card postings">
  <h2>Open postings</h2>
  <p class="note">Every posting links to the portal, where you read the ad and apply.</p>
  <div class="filters">
    <input id="q" type="search" placeholder="Search title, company or location" aria-label="Search postings">
    <select id="source" aria-label="Source"><option value="">All sources</option>{{source_options}}</select>
    <select id="sort" aria-label="Sort">
      <option value="listed">Newest first</option>
      <option value="deadline">Deadline soonest</option>
    </select>
  </div>
  <p class="count" id="count">{{posting_count}} postings</p>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>Title</th><th>Company</th><th>Location</th><th>Deadline</th><th>Listed</th><th>Source</th></tr></thead>
    <tbody id="rows">{{rows}}</tbody>
  </table>
  </div>
</section>

<footer id="about">
  <h2>How this works</h2>
  <p>Every day a script reads the student job listings on <a href="https://studerendeonline.dk">StuderendeOnline</a> and
  <a href="https://www.jobindex.dk">Jobindex</a>, and keeps the history. It follows each site's robots.txt and stores
  only the title, company, location, dates and the link, never the ad text or contact details.</p>
  <p>StuderendeOnline lists every student job in the Capital Region, so the figures above come from there.
  Jobindex shows at most 20 results per search, so its postings in the table are a sample.
  The same job can appear on both sites. "Listed" is the date the portal shows, which for StuderendeOnline is when the posting was last updated.</p>
  <p>Not affiliated with either portal. Code and data: <a href="{{repo}}">{{repo}}</a></p>
</footer>
</div>

<script>
(() => {
  const rows = [...document.querySelectorAll("#rows tr")];
  const tbody = document.getElementById("rows");
  const q = document.getElementById("q"), source = document.getElementById("source"), sort = document.getElementById("sort");
  const count = document.getElementById("count");
  function update() {
    const words = q.value.toLowerCase().split(/\\s+/).filter(Boolean);
    const key = sort.value;
    const sorted = rows.slice().sort((a, b) => key === "deadline"
      ? (a.dataset.deadline || "9999").localeCompare(b.dataset.deadline || "9999")
      : (b.dataset.listed || "").localeCompare(a.dataset.listed || ""));
    let shown = 0;
    for (const row of sorted) {
      const match = (!source.value || row.dataset.source === source.value)
        && words.every(w => row.dataset.search.includes(w));
      row.hidden = !match;
      shown += match;
      tbody.appendChild(row);
    }
    count.textContent = shown.toLocaleString("en") + (shown === 1 ? " posting" : " postings");
  }
  q.addEventListener("input", update); source.addEventListener("change", update); sort.addEventListener("change", update);

  const tip = document.createElement("div");
  tip.className = "tip"; tip.hidden = true; document.body.appendChild(tip);
  function show(value, label, x, y) {
    tip.replaceChildren();
    const strong = document.createElement("strong"); strong.textContent = value;
    const span = document.createElement("span"); span.textContent = label;
    tip.append(strong, span); tip.hidden = false;
    const r = tip.getBoundingClientRect();
    tip.style.left = Math.min(x + 12, innerWidth - r.width - 8) + "px";
    tip.style.top = Math.max(8, y - r.height - 12) + "px";
  }
  const hide = () => { tip.hidden = true; };
  for (const bar of document.querySelectorAll(".bar-row")) {
    bar.addEventListener("pointermove", ev => show(bar.dataset.tipValue, bar.dataset.tipLabel, ev.clientX, ev.clientY));
    bar.addEventListener("pointerleave", hide);
    bar.addEventListener("focus", () => { const r = bar.getBoundingClientRect(); show(bar.dataset.tipValue, bar.dataset.tipLabel, r.right - 80, r.top); });
    bar.addEventListener("blur", hide);
  }
  const svg = document.querySelector(".line-chart");
  if (svg) {
    const points = JSON.parse(svg.dataset.points), cross = svg.querySelector(".crosshair");
    svg.querySelector(".hit").addEventListener("pointermove", ev => {
      const pt = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(svg.getScreenCTM().inverse());
      const near = points.reduce((a, b) => Math.abs(b[2] - pt.x) < Math.abs(a[2] - pt.x) ? b : a);
      cross.setAttribute("x1", near[2]); cross.setAttribute("x2", near[2]); cross.setAttribute("visibility", "visible");
      show(near[1].toLocaleString("en") + " open", near[0], ev.clientX, ev.clientY);
    });
    svg.querySelector(".hit").addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hide(); });
  }
})();
</script>
</body>
</html>
"""
