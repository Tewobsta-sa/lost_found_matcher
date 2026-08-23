"""Non-interactive demo: populates a few reports and prints the matches.

Run with:  python demo.py
"""

from datetime import date

from lost_found.store import ReportStore


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    store = ReportStore()

    # --- Scenario from the prompt: AirPods case near the cafeteria ---
    lost_airpods = store.add_lost(
        "I lost my black AirPods case yesterday near the cafeteria.",
        location="cafeteria", date=date(2026, 8, 20),
    )
    found_case = store.add_found(
        "Found a dark wireless earbud case beside the coffee shop.",
        location="coffee shop", date=date(2026, 8, 20),
    )

    # --- Scenario from the prompt: library backpack (good match) ---
    lost_backpack = store.add_lost(
        "Black backpack containing a laptop charger. Lost around the "
        "library on Monday afternoon.",
        location="library", date=date(2026, 8, 17),
    )
    found_backpack_near = store.add_found(
        "Dark-colored backpack found near the library entrance Monday evening.",
        location="library entrance", date=date(2026, 8, 17),
    )

    # --- Scenario from the prompt: football field, two weeks later (weak/no match) ---
    found_backpack_far = store.add_found(
        "Black backpack found at the football field two weeks later.",
        location="football field", date=date(2026, 8, 31),
    )

    # --- A clean non-match: different item entirely ---
    found_umbrella = store.add_found(
        "Blue umbrella left in a lecture hall.",
        location="lecture hall", date=date(2026, 8, 18),
    )

    # --- Incomplete report: no location, no date ---
    lost_wallet = store.add_lost("Lost my brown wallet somewhere on campus.")
    found_wallet = store.add_found("Found a wallet, looks worn, brown leather.")

    section("All reports")
    for r in store.all():
        print(" ", r)

    section(f"Matches for Lost #{lost_airpods.id} (AirPods case)")
    for m in store.matches_for(lost_airpods):
        print()
        print(m)

    section(f"Matches for Lost #{lost_backpack.id} (backpack)")
    for m in store.matches_for(lost_backpack):
        print()
        print(m)

    section(f"Matches for Lost #{lost_wallet.id} (incomplete wallet report)")
    matches = store.matches_for(lost_wallet)
    if not matches:
        print("  (no matches above display threshold)")
    for m in matches:
        print()
        print(m)

    section("Note on the football-field found-backpack report")
    print(
        "It's included above in the backpack matches list (if it clears the "
        "display threshold) but should score noticeably lower than the "
        "library-entrance report, due to location and time mismatches — "
        "see the 'Why' notes on each result."
    )


if __name__ == "__main__":
    main()
