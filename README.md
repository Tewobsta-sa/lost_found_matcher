# Lost & Found Matcher

A small application that helps identify potential matches between lost-item
and found-item reports submitted by students. Pure Python standard library —
no dependencies to install.

## Running it

**UI (recommended):** open `lost_found_board.html` in any browser — no server or install
needed. It's a self-contained corkboard-style app: pin lost/found reports on either side,
click a card to see its ranked matches drawn as connecting strings (solid = strong,
dashed = possible, dotted = unlikely), with a "why" breakdown for each. It ships preloaded
with the example scenarios from the prompt; use "Clear board" to start from scratch. The
matching logic here is a straight JS port of `lost_found/matcher.py`, verified against the
same test cases (see `tests/test_matcher.py` and the parity notes below).

```bash
# Non-interactive demo (populates a few reports, prints matches)
python3 demo.py

# Interactive CLI
python3 -m lost_found.cli

# Tests
python3 -m unittest discover -v tests
```

## What it does

1. **Create reports.** `store.add_lost(...)` / `store.add_found(...)` (or
   the CLI's menu options 1/2) create a `Report` with a description and
   optional location, date, and contact info.
2. **See potential matches.** `store.matches_for(report)` (CLI option 4)
   compares a report against all reports of the opposite type and returns
   a ranked list of candidates above a display threshold, each labeled
   **Strong match**, **Possible match**, or (if you lower the threshold)
   **Unlikely match**, along with a short human-readable explanation of
   *why* it scored the way it did.

## How matching works

There's no single correct definition of "a match," so I made it an explicit,
inspectable decision: **a weighted combination of five independent
signals**, each scored 0–1:

| Signal   | Weight | What it checks |
|----------|-------:|-----------------|
| Category | 0.35   | Same *kind* of item (backpack, wallet, AirPods case, …), via a small keyword/synonym table |
| Color    | 0.15   | Do the mentioned colors agree — including loose terms like "dark" matching "black" |
| Location | 0.25   | Same/nearby location — via known campus-location keywords, substring containment, and fuzzy string matching as a fallback |
| Time     | 0.15   | Found-date should be on/after the lost-date, and close in time |
| Text     | 0.10   | Jaccard overlap of remaining words, as a catch-all for anything the structured signals miss |

The weighted scores combine into one number, which maps to a label:
**≥ 0.70 → Strong**, **≥ 0.45 → Possible**, otherwise dropped from the
results entirely (below 0.30) or shown as **Unlikely**.

Category gets the highest weight because "same object type" is the single
strongest indicator; location and time come next because they capture the
physical story of how an item could plausibly move from where it was lost
to where it was found. Pure text overlap is weighted lowest deliberately —
two unrelated reports can share a lot of incidental words ("near", "found
by", campus filler language), so it's a tiebreaker, not the main signal.

**Missing information is treated as neutral (0.5), not negative.** Most
real-world reports are incomplete — someone forgets to add a location, or
doesn't know the exact date. Penalizing missing data would bury genuinely
good matches just because a field was left blank. Only *information that
was provided and disagrees* (different item types, conflicting colors,
found-before-lost dates) pulls the score down.

### Worked example (from the prompt)

- *Lost*: "Black backpack containing a laptop charger... near the library
  on Monday afternoon" → *Found*: "Dark-colored backpack... near the
  library entrance Monday evening" scores **87%, Strong match** — same
  category, colors agree (dark ≈ black), same location, timing lines up.
- The same lost report against *Found*: "Black backpack found at the
  football field two weeks later" scores lower (**Possible match**, ~61%)
  — category and color still agree, but location and time signals pull it
  down. It's deliberately not thrown out entirely (it's still the same
  color/type of item and *could* be the same backpack), just ranked below
  the more consistent match — which mirrors how a human doing this by hand
  would likely triage it.

## Other design decisions & assumptions

- **Date is a separate structured field, not parsed from the description.**
  Reliably extracting "yesterday," "Monday afternoon," or "two weeks
  later" from free text is a substantial NLP problem on its own. I chose
  to keep the description as free text (for search/color/category
  extraction) and ask for the date separately, which is also how a real
  submission form would work (e.g., a date picker next to a text box).
- **The item ontology is a small hand-written keyword table**, not a
  trained classifier. This keeps the system's behavior transparent,
  debuggable, and dependency-free, which felt right for this scope. It's
  also the most obvious limitation — see below.
- **A report requires a non-empty description**; that's the one hard
  validation rule. Everything else (location, date, contact) is optional,
  reflecting that a partial report is still useful and shouldn't be
  rejected.
- **Matching is symmetric per pair, not global optimization.** Each
  lost/found pair is scored independently. I did *not* implement
  one-to-one assignment (e.g., "once found item A is claimed as the best
  match for lost item B, don't also suggest A for lost item C"), since
  that's a real but separate problem (bipartite matching) and the prompt
  asks for identifying *potential* matches, which is naturally many-to-many
  until a human confirms one.
- **Storage is in-memory**, with optional JSON save/load for convenience.
  A real deployment would use a database; that's out of scope here.

## What I'd improve with more time

- **Semantic similarity instead of keyword matching.** The category/color
  ontology is easy to reason about but brittle — it won't recognize "tote
  bag" as similar to "backpack" unless I add it by hand. Swapping in
  sentence embeddings (e.g., cosine similarity over an embedding model)
  for the category and text signals would generalize much better, at the
  cost of transparency and a new dependency.
- **Photo support.** Lost-and-found matching in practice leans heavily on
  photos; even simple perceptual-hash comparison would likely outperform
  any text signal for color/shape.
- **One-to-one resolution / staff review workflow.** Once a human confirms
  a match, both reports should be marked "resolved" and removed from
  future candidate lists, with an audit trail.
- **Location taxonomy from real campus data** instead of a hardcoded
  keyword list, ideally with geographic coordinates so "50 meters apart"
  can be scored more precisely than "shared a keyword."
- **Basic web UI** (a form + results list) instead of a CLI, since that's
  closer to how students would actually interact with this.
- **Duplicate/spam detection** — right now nothing stops the same report
  from being submitted twice, or obviously fake reports (e.g. one-word
  descriptions) from being accepted, beyond the "must be non-empty" check.

## Project layout

```
lost_found_matcher/
├── demo.py                  # non-interactive walkthrough
├── lost_found/
│   ├── models.py            # Report data model
│   ├── matcher.py           # scoring engine (the interesting part)
│   ├── store.py             # in-memory storage + JSON persistence
│   └── cli.py                # interactive command-line interface
└── tests/
    └── test_matcher.py      # unit tests, including the prompt's examples
```
