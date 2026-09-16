from cphjobs.robots import RobotsRules

# Same rule shapes as the portals use, trimmed down.
ROBOTS = """
User-agent: *
Disallow: /api/
Disallow: /jobsoegning*geoareaid=
Disallow: /jobsoegning*page=
Disallow: /jobsoegning/*?*&
Allow: /job/
Disallow: /job/*?

User-agent: badbot
Disallow: /
"""


def test_search_page_with_one_parameter_is_allowed():
    rules = RobotsRules(ROBOTS)
    assert rules.allowed("/jobsoegning/storkoebenhavn?q=studiejob")


def test_wildcard_rules_block_the_rss_and_extra_parameters():
    rules = RobotsRules(ROBOTS)
    assert not rules.allowed("/jobsoegning.rss?geoareaid=15182&q=studiejob")
    assert not rules.allowed("/jobsoegning/storkoebenhavn?q=studiejob&page=2")
    assert not rules.allowed("/jobsoegning/storkoebenhavn?q=studiejob&format=rss")
    assert not rules.allowed("/api/v1/jobs")


def test_longest_match_wins():
    rules = RobotsRules(ROBOTS)
    assert rules.allowed("/job/123/some-company/some-title/")
    assert not rules.allowed("/job/123/?x=1")


def test_named_group_replaces_the_wildcard_group():
    assert not RobotsRules(ROBOTS, agent="BadBot/2.0").allowed("/anything")
    assert RobotsRules(ROBOTS, agent="copenhagen-student-jobs/0.1 (+https://github.com/x)").allowed(
        "/anything"
    )


def test_empty_robots_allows_everything():
    assert RobotsRules("").allowed("/anything?at=all")
