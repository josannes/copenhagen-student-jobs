"""One module per job portal. Each exposes `fetch(client) -> FetchResult`,
`detail_url(posting)` and `ad_text(page)`, and depends only on
`cphjobs.models` and `cphjobs.http`, so the collectors can be reused without the database."""

from . import jobindex, studerendeonline

MODULES = {module.NAME: module for module in (jobindex, studerendeonline)}
SOURCES = {name: module.fetch for name, module in MODULES.items()}
