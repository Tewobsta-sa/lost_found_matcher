"""A minimal interactive command-line interface for the Lost & Found Matcher."""

from __future__ import annotations

from datetime import date as Date, datetime

from .store import ReportStore

MENU = """
==== Lost & Found Matcher ====
1) Report a lost item
2) Report a found item
3) View all reports
4) View matches for a report
0) Exit
> """


def _prompt_date() -> Date | None:
    raw = input("Date (YYYY-MM-DD, blank if unknown): ").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        print("  Couldn't parse that date, leaving it blank.")
        return None


def _add_report(store: ReportStore, kind: str) -> None:
    description = input("Description: ").strip()
    if not description:
        print("  A description is required — report not saved.")
        return
    location = input("Location (optional): ").strip() or None
    date = _prompt_date()
    contact = input("Contact info (optional): ").strip() or None
    try:
        if kind == "lost":
            report = store.add_lost(description, location, date, contact)
        else:
            report = store.add_found(description, location, date, contact)
    except ValueError as e:
        print(f"  Error: {e}")
        return
    print(f"  Saved as {report}")


def _view_all(store: ReportStore) -> None:
    reports = store.all()
    if not reports:
        print("  No reports yet.")
        return
    for r in reports:
        print(f"  {r}")


def _view_matches(store: ReportStore) -> None:
    try:
        rid = int(input("Report ID to find matches for: ").strip())
    except ValueError:
        print("  Please enter a numeric report ID.")
        return
    report = store.get(rid)
    if not report:
        print("  No report found with that ID.")
        return
    matches = store.matches_for(report)
    if not matches:
        print("  No plausible matches found.")
        return
    for m in matches:
        print()
        print(m)


def main() -> None:
    store = ReportStore()
    actions = {"1": lambda: _add_report(store, "lost"),
               "2": lambda: _add_report(store, "found"),
               "3": lambda: _view_all(store),
               "4": lambda: _view_matches(store)}
    while True:
        choice = input(MENU).strip()
        if choice == "0":
            print("Goodbye.")
            break
        action = actions.get(choice)
        if action:
            action()
        else:
            print("  Not a valid option.")


if __name__ == "__main__":
    main()
