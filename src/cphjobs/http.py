"""A small, polite HTTP client: identifies itself, waits between requests, obeys robots.txt."""

import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .robots import RobotsRules

log = logging.getLogger(__name__)

USER_AGENT = "copenhagen-student-jobs/0.1 (+https://github.com/josannes/copenhagen-student-jobs)"


class DisallowedByRobots(Exception):
    pass


class ExternalRedirect(Exception):
    """The page redirects to another site, whose robots.txt and terms we haven't checked."""


class _GuardedRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, client: "PoliteClient"):
        self.client = client

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if new.netloc != old.netloc:
            raise ExternalRedirect(newurl)
        if not self.client.allowed(newurl):
            raise DisallowedByRobots(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PoliteClient:
    def __init__(self, delay: float = 3.0, timeout: float = 30.0):
        self.delay = delay
        self.timeout = timeout
        self._robots: dict[str, RobotsRules] = {}
        self._last_request: dict[str, float] = {}
        self._opener = urllib.request.build_opener(_GuardedRedirects(self))

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        return self._rules_for(f"{parts.scheme}://{parts.netloc}").allowed(path)

    def get(self, url: str) -> str:
        """Fetch a page. Raises DisallowedByRobots, ExternalRedirect or urllib's HTTPError."""
        if not self.allowed(url):
            raise DisallowedByRobots(url)
        parts = urlsplit(url)
        return self._fetch(url, f"{parts.scheme}://{parts.netloc}")

    def _rules_for(self, host: str) -> RobotsRules:
        if host not in self._robots:
            try:
                text = self._fetch(f"{host}/robots.txt", host)
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                text = ""  # no robots.txt means no restrictions
            self._robots[host] = RobotsRules(text, agent=USER_AGENT)
        return self._robots[host]

    def _fetch(self, url: str, host: str, attempts: int = 2) -> str:
        for attempt in range(1, attempts + 1):
            wait = self._last_request.get(host, 0) + self.delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request[host] = time.monotonic()
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == attempts:
                    raise
                log.warning("HTTP %s from %s, retrying", e.code, url)
            except urllib.error.URLError as e:
                if attempt == attempts:
                    raise
                log.warning("%s from %s, retrying", e.reason, url)
        raise AssertionError("unreachable")
