"""One module per job portal. Each exposes `fetch(client) -> FetchResult` and depends only on
`cphjobs.models` and `cphjobs.http`, so the collectors can be reused without the database."""

from . import jobindex, studerendeonline

SOURCES = {
    jobindex.NAME: jobindex.fetch,
    studerendeonline.NAME: studerendeonline.fetch,
}
