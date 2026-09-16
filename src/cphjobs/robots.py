"""robots.txt rules with wildcard support.

Python's urllib.robotparser only does prefix matching, but the portals use `*` wildcards
(Jobindex disallows `/jobsoegning*geoareaid=`, for example). This follows the matching
rules in RFC 9309: the longest matching rule wins, and Allow wins a tie.
"""

import re


def _to_regex(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    body = ".*".join(re.escape(part) for part in pattern.split("*"))
    return re.compile(body + ("$" if anchored else ""))


class RobotsRules:
    def __init__(self, text: str, agent: str = "*"):
        self.rules: list[tuple[bool, str, re.Pattern[str]]] = []
        groups: list[tuple[list[str], list[tuple[str, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[str, str]] = []

        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if rules:
                    groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(value.lower())
            elif key in ("allow", "disallow") and agents:
                rules.append((key, value))
        if agents:
            groups.append((agents, rules))

        product = agent.split("/", 1)[0].strip().lower()  # "name/1.0 (+url)" -> "name"
        chosen = [r for a, r in groups if product in a]
        if not chosen:
            chosen = [r for a, r in groups if "*" in a]

        for group in chosen:
            for key, value in group:
                if value:  # an empty Disallow means "allow everything"
                    self.rules.append((key == "allow", value, _to_regex(value)))

    def allowed(self, path: str) -> bool:
        """`path` is the path plus query string, e.g. `/jobsoegning/storkoebenhavn?q=x`."""
        best_len, best_allow = -1, True
        for allow, pattern, regex in self.rules:
            if regex.match(path):
                if len(pattern) > best_len or (len(pattern) == best_len and allow):
                    best_len, best_allow = len(pattern), allow
        return best_allow
