from datetime import date

from cphjobs.clean import clean, hidden_reason

AS_OF = date(2026, 10, 17)


def posting(id, title="Studentermedhjælper til analyse og data i Eksempel", source="studerendeonline", **changes):
    base = dict(
        source=source, source_id=id, title=title, url=f"https://example.org/{source}/{id}", company="Eksempel A/S",
        listed="2026-10-10", deadline=None, deadline_kind="asap", details_status=None,
    )
    return base | changes


def test_old_postings_are_left_out():
    assert hidden_reason(posting("1", listed="2026-06-01"), AS_OF) == "stale"
    assert hidden_reason(posting("2", listed="2026-08-01"), AS_OF) is None


def test_jobs_in_other_cities_are_left_out():
    assert hidden_reason(posting("1", title="Studentermedhjælper til vores kontor i Odense"), AS_OF) == "elsewhere"
    assert hidden_reason(posting("2", title="Student Assistant: Copenhagen, Aarhus or Aalborg"), AS_OF) is None
    # The university's name doesn't say where the job is.
    assert hidden_reason(posting("3", title="Studentermedhjælper til Aalborg Universitet"), AS_OF) is None
    # Nor does a word that only contains a city name.
    assert hidden_reason(posting("4", title="Studenterstudievejledere søges"), AS_OF) is None


def test_phd_positions_and_events_are_left_out():
    assert hidden_reason(posting("1", title="PhD scholarship in Example Studies"), AS_OF) == "not_a_job"
    assert hidden_reason(posting("2", title="Ph.d.-stipendium i eksempler"), AS_OF) == "not_a_job"
    assert hidden_reason(posting("3", title="Step inside: An Evening for IT Students"), AS_OF) == "not_a_job"
    assert hidden_reason(posting("4", title="Student Assistant for our events team"), AS_OF) is None


def test_a_job_on_both_portals_is_one_row():
    so = posting("1", company="Eksempel", details_status="ok")
    ji = posting("h1", source="jobindex", company="Eksempel ApS", deadline="2026-10-30", deadline_kind="date")
    shown, hidden = clean([ji, so], AS_OF)
    (job,) = shown
    assert job["source"] == "studerendeonline"
    assert job["also"] == [("jobindex", "https://example.org/jobindex/h1")]
    assert job["deadline"] == "2026-10-30"  # taken from the copy that gives a date
    assert hidden["duplicate"] == 1


def test_short_titles_need_the_same_company_and_deadline():
    a = posting("1", title="Student Assistant", company="Eksempel A/S")
    b = posting("2", title="Student Assistant", company="Demo ApS")
    c = posting("3", title="Student Assistant", company="Eksempel", deadline="2026-11-01", deadline_kind="date")
    d = posting("4", title="Student Assistant", company="EKSEMPEL A/S")
    shown, hidden = clean([a, b, c, d], AS_OF)
    assert len(shown) == 3 and hidden["duplicate"] == 1


def test_a_repost_on_the_same_portal_counts_once():
    shown, _ = clean([posting("1", listed="2026-10-05"), posting("2", listed="2026-10-12")], AS_OF)
    (job,) = shown
    assert job["source_id"] == "2" and job["also"] == []
