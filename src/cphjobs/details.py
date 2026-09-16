"""Read the facts students ask about out of a posting's text: language, whether Danish is
required, hours per week and hourly pay.

Plain rules, no model, so every result can be traced back to a phrase. The text itself is
never stored; only what these functions return.
"""

import re
from dataclasses import dataclass

DANISH_WORDS = set("og at til med du er vi som af på det har kan en der os vores din dig skal hos om eller ikke ved de den".split())
ENGLISH_WORDS = set("and the to with you are we as of on it have can a our your will be is or not at who this that".split())


@dataclass(frozen=True)
class Details:
    language: str | None  # "da" or "en"
    danish: str | None  # "required", "optional" (an advantage or explicitly not required) or None
    hours_min: float | None
    hours_max: float | None
    pay_min: float | None  # DKK per hour
    pay_max: float | None
    pay_kind: str | None  # "stated", "agreement" (collective agreement, no amount) or None


def extract(text: str) -> Details:
    hours = hours_per_week(text)
    pay_min, pay_max, pay_kind = hourly_pay(text)
    return Details(language(text), danish_requirement(text), *hours, pay_min, pay_max, pay_kind)


def language(text: str) -> str | None:
    words = re.findall(r"[a-zæøå]+", text.lower())
    da = sum(w in DANISH_WORDS for w in words)
    en = sum(w in ENGLISH_WORDS for w in words)
    if da + en < 10:
        return None
    return "da" if da > en else "en"


# ---------------------------------------------------------------- Danish

S = r"[^.;:!?•·]"  # within one sentence or list item

OPTIONAL = [
    rf"\bdanish\b{S}{{0,40}}\b(not|no)\b{S}{{0,10}}\b(a )?(requirement|required|necessary|needed|must)\b",
    rf"\b(no|without)\b{S}{{0,15}}\bdanish\b",
    rf"\bdanish\b{S}{{0,40}}\b(advantage|a plus|bonus|an asset|nice to have|preferred|beneficial|welcome)\b",
    rf"\bdansk\b{S}{{0,40}}\b(er en fordel|er et plus|ikke et krav|ikke påkrævet|ikke nødvendig)",
    rf"\b(ikke|intet) krav om\b{S}{{0,15}}\bdansk\b",
]
REQUIRED = [
    rf"\b(fluent|fluency|proficient|proficiency|native)\b{S}{{0,30}}\bdanish\b",
    r"\b(excellent|strong|good|solid)\s+(written and spoken\s+|spoken and written\s+)?danish\b",
    r"\bdanish\s+(language\s+)?skills\b",
    rf"\bdanish\b{S}{{0,40}}\b(fluent|fluently|native|required|requirement|a must|mandatory|written and spoken|spoken and written|is essential)\b",
    rf"\b(speak|speaks|speaking|write|writes)\b{S}{{0,20}}\bdanish\b",
    r"\bdanish\s*-?\s*speaking\b",
    rf"\b(flydende|fejlfrit|fejlfri|sikkert|velformuleret|skribent|perfekt|styr på)\b{S}{{0,40}}\bdansk\b",
    rf"\b(taler|skriver|behersker|kommuniker\w*|formulere dig|skrive|tale|læse)\b{S}{{0,40}}\bdansk\b",
    rf"\b(skriftligt|mundtligt)\b{S}{{0,40}}\bdansk\b",
    rf"\bdansk\b{S}{{0,30}}\b(skriftligt og mundtligt|mundtligt og skriftligt|i skrift og tale|på modersmålsniveau|er et krav|er en forudsætning)",
]


def danish_requirement(text: str) -> str | None:
    t = re.sub(r"\bdansk tegnsprog\b", "tegnsprog", text.lower())  # Danish sign language is a different skill
    if any(re.search(p, t) for p in OPTIONAL):
        return "optional"
    if any(re.search(p, t) for p in REQUIRED):
        return "required"
    return None


# ---------------------------------------------------------------- hours

NUM = r"(\d{1,2}(?:[.,]5)?)"
RANGE = rf"(?:mellem\s+|between\s+)?{NUM}(?:\s*(?:-|–|til|to|og|and)\s*{NUM})?"
UNIT = r"(?:timer|hours|t\.)"
WEEK = r"(?:arbejdsuge|om ugen|pr\.? ?uge|per uge|i ugen|ugentlig\w*|a week|per week|each week|every week|weekly|/\s*week|/\s*uge|om\s+ugen)"
HOURS_PATTERNS = [
    rf"{RANGE}\s*{UNIT}{S}{{0,30}}?{WEEK}",  # "15-20 timer om ugen", "10-15 timer fordelt på 2-3 dage om ugen"
    rf"(?:ugentlig\w*|weekly){S}{{0,60}}?{RANGE}\s*{UNIT}",  # "Den ugentlige arbejdstid er 15 timer"
]


def _num(s: str | None) -> float | None:
    return float(s.replace(",", ".")) if s else None


def hours_per_week(text: str) -> tuple[float | None, float | None]:
    t = text.lower()
    for pattern in HOURS_PATTERNS:
        for m in re.finditer(pattern, t):
            low, high = _num(m[1]), _num(m[2]) or _num(m[1])
            if low and 1 <= low <= high <= 40:
                return low, high
    return None, None


# ---------------------------------------------------------------- pay

AMOUNT = r"(\d{2,3}(?:[.,]\d{1,2})?)"
CURRENCY = r"(?:dkk|kr\.?)"
MONEY = rf"(?:{CURRENCY}\s*{AMOUNT}|{AMOUNT}\s*{CURRENCY})(?:\s*(?:-|–|til|to)\s*(?:{CURRENCY}\s*{AMOUNT}|{AMOUNT}\s*{CURRENCY}?))?"
HOURLY = r"(?:\btimeløn\w*|\bhourly\s+(?:wage|rate|salary|pay)|\bløn\b|\bsalary\b|\bwage\b|\bpay\b)"
PER_HOUR = r"(?:i timen|pr\.? ?time|per time|per hour|an hour|/\s*time|/\s*hour)"
AGREEMENT = r"(overenskomst|collective agreement|hk/stat|hk/state)"


def hourly_pay(text: str) -> tuple[float | None, float | None, str | None]:
    t = text.lower()
    gap = r"[^.;!?•·]"  # like S, but "Løn: 150 kr" keeps its colon
    for pattern in (rf"{HOURLY}{gap}{{0,40}}?{MONEY}", rf"{MONEY}\s*{PER_HOUR}"):
        for m in re.finditer(pattern, t):
            amounts = [_num(g) for g in m.groups() if g]
            if amounts and all(100 <= a <= 400 for a in amounts):  # student hourly pay, not totals
                return min(amounts), max(amounts), "stated"
    if re.search(AGREEMENT, t):
        return None, None, "agreement"
    return None, None, None
