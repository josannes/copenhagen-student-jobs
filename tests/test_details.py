import pytest

from cphjobs.details import danish_requirement, extract, hourly_pay, hours_per_week, language

# All sentences are written for these tests, in the styles the portals use.


def test_language():
    assert language("Vi søger en studentermedhjælper, der har lyst til at arbejde med data og som kan lide at løse opgaver i et team.") == "da"
    assert language("We are looking for a student assistant who will work with our data team and have a passion for analytics in the office.") == "en"
    assert language("Studentermedhjælper") is None  # too little text to tell


@pytest.mark.parametrize(
    "text, expected",
    [
        ("You speak and write fluent Danish and English.", "required"),
        ("Fluency in Danish is a requirement for this role.", "required"),
        ("We are hiring Danish-speaking students for our sales team.", "required"),
        ("Du taler og skriver flydende dansk.", "required"),
        ("Du kommunikerer klart på både dansk og engelsk.", "required"),
        ("Dansk i skrift og tale er en forudsætning.", "required"),
        ("Fluent English. Danish is an advantage but not a requirement.", "optional"),
        ("Knowledge of Danish is a plus.", "optional"),
        ("No Danish needed, our office language is English.", "optional"),
        ("Kendskab til dansk er en fordel.", "optional"),
        ("We are a Danish company based in Copenhagen.", None),
        ("You must be enrolled at a Danish university.", None),
        ("Du bliver en del af en dansk virksomhed.", None),
        ("Borgeren kommunikerer på dansk tegnsprog.", None),
    ],
)
def test_danish_requirement(text, expected):
    assert danish_requirement(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Arbejdstid: 15-20 timer om ugen.", (15, 20)),
        ("Du arbejder ca. 12 timer pr. uge.", (12, 12)),
        ("10-15 timer fordelt på 2-3 dage om ugen", (10, 15)),
        ("Den ugentlige arbejdstid er som udgangspunkt 18 timer.", (18, 18)),
        ("Stillingen er mellem 7,5 og 15 timer ugentligt.", (7.5, 15)),
        ("En 15 timers arbejdsuge med fleksibilitet.", (15, 15)),
        ("Part-time (10-15 hours/week)", (10, 15)),
        ("You will work approximately 20 hours per week.", (20, 20)),
        ("Omkring 30 timer pr. semester.", (None, None)),
        ("250 timer årligt.", (None, None)),
        ("Working hours are between 8 and 16 on weekdays.", (None, None)),
    ],
)
def test_hours_per_week(text, expected):
    assert hours_per_week(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Timeløn 150,50 kr. plus pension.", (150.5, 150.5, "stated")),
        ("The hourly wage ranges from DKK 140 - 160 depending on seniority.", (140, 160, "stated")),
        ("Løn: 175 kr (inkl. grundløn på 160 kr.)", (175, 175, "stated")),
        ("Du får 200 kr. i timen.", (200, 200, "stated")),
        ("Løn efter gældende overenskomst.", (None, None, "agreement")),
        ("Vi har en omsætning på 40 milliarder kr.", (None, None, None)),
        ("Salary: DKK 25.000 per month", (None, None, None)),
    ],
)
def test_hourly_pay(text, expected):
    assert hourly_pay(text) == expected


def test_extract_combines_everything():
    d = extract(
        "We are looking for a student assistant to join our analytics team in Copenhagen. "
        "You are fluent in English, and Danish is an advantage. The role is 15-20 hours per week. "
        "The hourly wage is DKK 165."
    )
    assert (d.language, d.danish, d.hours_min, d.hours_max, d.pay_min, d.pay_kind) == ("en", "optional", 15, 20, 165, "stated")
