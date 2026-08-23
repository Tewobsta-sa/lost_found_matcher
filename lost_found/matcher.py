"""Matching engine.

There is no single, objectively "correct" definition of a match between a
lost report and a found report, so this module makes an explicit, documented
choice: a match is a *weighted combination of independent signals*, each of
which is easy to reason about on its own:

    1. Item category   (is it plausibly the same *kind* of object?)
    2. Color            (do the described colors agree, even loosely?)
    3. Location          (were they lost/found near each other?)
    4. Time              (does the timing make sense — found on/after lost?)
    5. General text overlap (a catch-all for anything the above miss)

Each signal returns a score in [0, 1], where 0.5 means "unknown / not
enough information to judge" rather than "bad". Treating missing
information as neutral (instead of as a penalty) matters a lot in practice:
most real reports are incomplete, and a good matcher shouldn't punish a
report just because someone forgot to fill in the location field.

The signals are then combined with fixed weights into a single score, and
the score is translated into a human-readable label (Strong / Possible /
Unlikely). The weights and thresholds are judgment calls — they're grouped
together near the top of the file so they're easy to find and tune.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Set

from .models import Report, ReportType

# ---------------------------------------------------------------------------
# Tunable weights & thresholds
# ---------------------------------------------------------------------------

WEIGHTS = {
    "category": 0.35,
    "color": 0.15,
    "location": 0.25,
    "time": 0.15,
    "text": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

STRONG_THRESHOLD = 0.70
POSSIBLE_THRESHOLD = 0.45
# Anything scoring below this isn't shown at all — it's noise.
DISPLAY_THRESHOLD = 0.30

# ---------------------------------------------------------------------------
# Small hand-built ontology.
#
# This is intentionally simple (a keyword lookup, not a trained model) so
# that its behavior is transparent and predictable — appropriate for the
# scope of this exercise. See README for how this could be swapped for an
# embedding-based approach later without changing the rest of the pipeline.
# ---------------------------------------------------------------------------

ITEM_SYNONYMS: Dict[str, List[str]] = {
    "bag": ["backpack", "bag", "rucksack", "knapsack", "tote", "duffel", "duffel bag"],
    "earbuds/case": [
        "airpods", "airpods case", "earbud", "earbuds", "earbud case",
        "earbuds case", "earphone", "earphones", "earphone case",
        "wireless earbud case", "headphones",
    ],
    "wallet": ["wallet", "billfold", "purse", "coin purse"],
    "phone": ["phone", "cell phone", "cellphone", "smartphone", "iphone", "android phone"],
    "laptop": ["laptop", "notebook computer", "macbook", "chromebook"],
    "keys": ["keys", "key", "keychain", "key fob", "car key", "car keys"],
    "umbrella": ["umbrella"],
    "bottle": ["water bottle", "bottle", "flask", "thermos"],
    "eyewear": ["glasses", "sunglasses", "spectacles", "eyeglasses"],
    "outerwear": ["jacket", "coat", "hoodie", "sweater", "sweatshirt", "windbreaker"],
    "id/card": ["id card", "student id", "id badge", "badge", "card", "id"],
    "charger/cable": ["charger", "charging cable", "cable", "cord", "power bank", "power cord"],
    "notebook": ["notebook", "notepad", "planner", "journal"],
    "watch": ["watch", "smartwatch", "wristwatch"],
    "umbrella_": [],  # placeholder kept out of iteration below (unused)
}
# Drop empty placeholder entries.
ITEM_SYNONYMS = {k: v for k, v in ITEM_SYNONYMS.items() if v}

COLOR_WORDS = {
    "black", "white", "gray", "grey", "blue", "red", "green", "yellow",
    "brown", "pink", "purple", "orange", "silver", "gold", "navy",
    "beige", "tan", "maroon", "teal",
}
COLOR_NORMALIZE = {"grey": "gray"}
DARK_COLORS = {"black", "gray", "navy", "brown", "maroon", "purple"}
LIGHT_COLORS = {"white", "beige", "tan", "silver", "yellow"}
VAGUE_DARK = {"dark", "dark-colored", "dark colored"}
VAGUE_LIGHT = {"light", "light-colored", "light colored"}

KNOWN_LOCATIONS = [
    "cafeteria", "coffee shop", "library", "library entrance", "gym",
    "dorm", "dormitory", "residence hall", "football field", "quad",
    "student center", "student union", "parking lot", "bus stop",
    "lecture hall", "auditorium", "science building", "engineering building",
    "dining hall", "bookstore", "gymnasium", "stadium", "lab", "classroom",
]

STOPWORDS = {
    "a", "an", "the", "i", "my", "me", "near", "by", "beside", "around",
    "found", "lost", "yesterday", "today", "this", "that", "and", "or",
    "on", "in", "at", "of", "to", "it", "was", "is", "with", "containing",
    "contains", "morning", "afternoon", "evening", "night", "last",
    "week", "weeks", "day", "days", "ago", "later", "some", "somewhere",
}

_WORD_RE = re.compile(r"[a-zA-Z']+")


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def _content_tokens(text: str) -> Set[str]:
    return {w for w in _tokenize(text) if w not in STOPWORDS and len(w) > 2}


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

def extract_categories(text: str) -> Set[str]:
    """Return the set of item categories mentioned in free text.

    Uses substring matching against the synonym table above. A report can
    plausibly mention more than one item category (e.g. "backpack
    containing a laptop charger"), so we return a set rather than a single
    best guess -- that also naturally supports the library-backpack example
    where "laptop charger" is a secondary detail, not the lost item itself.
    """
    lowered = f" {text.lower()} "
    found: Set[str] = set()
    for canonical, synonyms in ITEM_SYNONYMS.items():
        for phrase in synonyms:
            if f" {phrase} " in lowered or lowered.startswith(f"{phrase} ") or lowered.endswith(f" {phrase} "):
                found.add(canonical)
                break
            # also allow the phrase to appear without surrounding spaces
            # guaranteed (e.g. at punctuation boundaries)
            if re.search(rf"\b{re.escape(phrase)}\b", text.lower()):
                found.add(canonical)
                break
    return found


def extract_colors(text: str) -> Set[str]:
    tokens = set(_tokenize(text))
    colors = set()
    for tok in tokens:
        norm = COLOR_NORMALIZE.get(tok, tok)
        if norm in COLOR_WORDS:
            colors.add(norm)
    lowered = text.lower()
    for phrase in VAGUE_DARK:
        if phrase in lowered:
            colors.add("dark")
    for phrase in VAGUE_LIGHT:
        if phrase in lowered:
            colors.add("light")
    return colors


def extract_locations(text: str) -> Set[str]:
    lowered = text.lower()
    return {loc for loc in KNOWN_LOCATIONS if loc in lowered}


# ---------------------------------------------------------------------------
# Per-signal scoring (each returns a float in [0, 1])
# ---------------------------------------------------------------------------

def score_category(cats_a: Set[str], cats_b: Set[str]) -> float:
    if cats_a & cats_b:
        return 1.0
    if not cats_a or not cats_b:
        return 0.5  # unknown category on at least one side -> neutral
    return 0.0  # both identified, and they disagree -> real negative signal


def score_color(colors_a: Set[str], colors_b: Set[str]) -> float:
    specific_a = colors_a - {"dark", "light"}
    specific_b = colors_b - {"dark", "light"}
    if specific_a & specific_b:
        return 1.0
    if ("dark" in colors_a and specific_b & DARK_COLORS) or \
       ("dark" in colors_b and specific_a & DARK_COLORS):
        return 0.6
    if ("light" in colors_a and specific_b & LIGHT_COLORS) or \
       ("light" in colors_b and specific_a & LIGHT_COLORS):
        return 0.6
    if "dark" in colors_a and "dark" in colors_b:
        return 0.6
    if "light" in colors_a and "light" in colors_b:
        return 0.6
    if not colors_a or not colors_b:
        return 0.5  # no color mentioned on at least one side -> neutral
    return 0.0  # colors mentioned on both sides and they conflict


def score_location(loc_a: Optional[str], loc_b: Optional[str]) -> float:
    if not loc_a or not loc_b:
        return 0.5
    known_a, known_b = extract_locations(loc_a), extract_locations(loc_b)
    if known_a & known_b:
        return 1.0
    a, b = loc_a.lower().strip(), loc_b.lower().strip()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.8
    ratio = SequenceMatcher(None, a, b).ratio()
    # Scale down fuzzy string similarity -- coincidental character overlap
    # shouldn't score as high as a genuine keyword/substring match.
    return max(0.0, min(ratio, 0.7))


def score_time(date_a, date_b) -> float:
    if not date_a or not date_b:
        return 0.5
    # A "found" report logically can't predate the corresponding "lost"
    # report by much; treat that as a strong negative signal rather than
    # just "far apart in time".
    delta_days = (date_b - date_a).days
    if delta_days < -1:
        return 0.05
    diff = abs(delta_days)
    if diff <= 0:
        return 1.0
    if diff <= 1:
        return 0.9
    if diff <= 3:
        return 0.7
    if diff <= 7:
        return 0.5
    if diff <= 14:
        return 0.3
    return 0.1


def score_text(text_a: str, text_b: str) -> float:
    tokens_a, tokens_b = _content_tokens(text_a), _content_tokens(text_b)
    if not tokens_a or not tokens_b:
        return 0.5
    union = tokens_a | tokens_b
    if not union:
        return 0.5
    jaccard = len(tokens_a & tokens_b) / len(union)
    return jaccard


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    lost: Report
    found: Report
    score: float
    label: str
    breakdown: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        pct = f"{self.score * 100:.0f}%"
        lines = [f"[{self.label}] ({pct}) Lost #{self.lost.id} <-> Found #{self.found.id}"]
        lines.append(f"  Lost : {self.lost.description}")
        lines.append(f"  Found: {self.found.description}")
        if self.notes:
            lines.append("  Why: " + "; ".join(self.notes))
        return "\n".join(lines)


def _label_for(score: float) -> str:
    if score >= STRONG_THRESHOLD:
        return "Strong match"
    if score >= POSSIBLE_THRESHOLD:
        return "Possible match"
    return "Unlikely match"


def compare(lost: Report, found: Report) -> MatchResult:
    if lost.type != ReportType.LOST or found.type != ReportType.FOUND:
        raise ValueError("compare() expects a LOST report and a FOUND report.")

    cats_a, cats_b = extract_categories(lost.description), extract_categories(found.description)
    colors_a, colors_b = extract_colors(lost.description), extract_colors(found.description)

    breakdown = {
        "category": score_category(cats_a, cats_b),
        "color": score_color(colors_a, colors_b),
        "location": score_location(lost.location, found.location),
        "time": score_time(lost.date, found.date),
        "text": score_text(lost.description, found.description),
    }
    total = sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS)

    notes = []
    shared_cats = cats_a & cats_b
    if shared_cats:
        notes.append(f"same item type ({', '.join(sorted(shared_cats))})")
    elif cats_a and cats_b:
        notes.append(f"different item types ({', '.join(sorted(cats_a))} vs {', '.join(sorted(cats_b))})")

    if breakdown["color"] >= 0.6:
        notes.append("colors agree")
    elif colors_a and colors_b and breakdown["color"] == 0.0:
        notes.append("colors conflict")

    if breakdown["location"] >= 0.8:
        notes.append("same/nearby location")
    elif lost.location and found.location and breakdown["location"] < 0.4:
        notes.append("locations don't seem related")

    if breakdown["time"] <= 0.1 and lost.date and found.date:
        notes.append("found date is before the lost date (suspicious)")
    elif breakdown["time"] >= 0.7:
        notes.append("timing lines up well")

    return MatchResult(lost=lost, found=found, score=total, label=_label_for(total), breakdown=breakdown, notes=notes)


def find_matches(target: Report, candidates: Iterable[Report],
                  threshold: float = DISPLAY_THRESHOLD) -> List[MatchResult]:
    """Find and rank potential matches for `target` among `candidates`.

    `target` can be either a LOST or a FOUND report; `candidates` should be
    reports of the opposite type (mixed lists are filtered automatically).
    """
    results = []
    for other in candidates:
        if other.type == target.type:
            continue
        lost, found = (target, other) if target.type == ReportType.LOST else (other, target)
        result = compare(lost, found)
        if result.score >= threshold:
            results.append(result)
    results.sort(key=lambda r: r.score, reverse=True)
    return results
