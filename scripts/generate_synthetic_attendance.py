"""Generate long-format synthetic weekly attendance data.

Target shape:
- Weekly dates from the first Sunday on/after 2025-01-01 through the most
  recent Sunday on or before today (covers all of 2025 and 2026 to date).
- Roughly 100 attendees per week.
- A stable core of about 70 people (high overall attendance rate).
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "synthetic_attendance.csv"


def last_sunday_on_or_before(day: date) -> date:
    # Monday=0 ... Sunday=6
    return day - timedelta(days=(day.weekday() + 1) % 7)


def first_sunday_on_or_after(day: date) -> date:
    return day + timedelta(days=(6 - day.weekday()) % 7)


def sunday_weeks(start: date, end: date) -> list[date]:
    """Inclusive list of Sundays from start to end (both should be Sundays)."""
    weeks: list[date] = []
    cur = start
    while cur <= end:
        weeks.append(cur)
        cur += timedelta(weeks=1)
    return weeks


def build_profiles() -> list[tuple[str, float]]:
    """Person IDs with base attendance probabilities.

    Expected weekly headcount ≈
      70 * 0.92 + 50 * 0.42 + 90 * 0.12 ≈ 64 + 21 + 11 ≈ 96
    Core at threshold 0.6 is dominated by the first band (~70 people).
    """
    profiles: list[tuple[str, float]] = []
    # Core regulars — nearly always present
    for i in range(1, 71):
        # slight spread so rates are not identical
        rate = 0.88 + (i % 7) * 0.01  # 0.88–0.94
        profiles.append((f"P{i:03d}", rate))
    # Occasional / mid-frequency
    for i in range(71, 121):
        rate = 0.32 + (i % 9) * 0.02  # ~0.32–0.48
        profiles.append((f"P{i:03d}", rate))
    # Rare / fringe attendees (inflates unique people, small weekly impact)
    for i in range(121, 211):
        rate = 0.06 + (i % 8) * 0.015  # ~0.06–0.165
        profiles.append((f"P{i:03d}", rate))
    return profiles


def main(today: date | None = None) -> None:
    random.seed(42)
    today = today or date.today()

    start = first_sunday_on_or_after(date(2025, 1, 1))
    end = last_sunday_on_or_before(today)
    if end < start:
        raise ValueError(f"No Sundays between {start} and {end}")

    weeks = sunday_weeks(start, end)
    n_weeks = len(weeks)
    profiles = build_profiles()

    rows: list[dict[str, str]] = []
    for person, base_rate in profiles:
        for wi, week in enumerate(weeks):
            p = base_rate
            # Mild seasonal dip around late December / early January weeks
            if week.month == 12 and week.day >= 20:
                p *= 0.75
            if week.month == 1 and week.day <= 7:
                p *= 0.85
            # Recent drift for a subset (rising / falling) so recency charts move
            in_recent = wi >= max(0, n_weeks - 12)
            if in_recent and person.endswith(("3", "7", "9")):
                p = min(1.0, p + 0.12)
            if in_recent and person.endswith(("2", "5")):
                p = max(0.0, p - 0.12)
            if random.random() < p:
                rows.append({"week": week.isoformat(), "person": person})

    df = pl.DataFrame(rows).sort(["week", "person"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(OUT)

    weekly = df.group_by("week").len().sort("week")
    rates = (
        df.group_by("person")
        .len()
        .with_columns((pl.col("len") / n_weeks).alias("rate"))
    )
    core60 = rates.filter(pl.col("rate") >= 0.6).height

    print(f"wrote {OUT}")
    print(f"  date range : {weeks[0]} → {weeks[-1]} ({n_weeks} Sundays)")
    print(f"  rows       : {df.height}")
    print(f"  people     : {df['person'].n_unique()}")
    print(
        f"  weekly     : mean={weekly['len'].mean():.1f} "
        f"median={weekly['len'].median():.1f} "
        f"min={weekly['len'].min()} max={weekly['len'].max()}"
    )
    print(f"  core ≥0.6  : {core60} people")


if __name__ == "__main__":
    main()
