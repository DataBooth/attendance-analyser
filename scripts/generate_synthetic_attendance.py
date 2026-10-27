"""Generate long-format synthetic weekly attendance data.

Target shape:
- Sundays from first Sunday on/after 2025-01-01 through last Sunday on/before today
- Roughly 100 attendees per week and a stable core of about 70
- Explicit life-cycle patterns for pastoral care-pack demos (absence, decline,
  new sticky, new fading, returnees, emerging regulars)
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "synthetic_attendance.csv"


def last_sunday_on_or_before(day: date) -> date:
    return day - timedelta(days=(day.weekday() + 1) % 7)


def first_sunday_on_or_after(day: date) -> date:
    return day + timedelta(days=(6 - day.weekday()) % 7)


def sunday_weeks(start: date, end: date) -> list[date]:
    weeks: list[date] = []
    cur = start
    while cur <= end:
        weeks.append(cur)
        cur += timedelta(weeks=1)
    return weeks


def add_attendance(
    rows: list[dict[str, str]], person: str, week: date
) -> None:
    rows.append({"week": week.isoformat(), "person": person})


def main(today: date | None = None) -> None:
    random.seed(42)
    today = today or date.today()

    start = first_sunday_on_or_after(date(2025, 1, 1))
    end = last_sunday_on_or_before(today)
    weeks = sunday_weeks(start, end)
    n_weeks = len(weeks)
    if n_weeks < 20:
        raise ValueError("Need a longer date range for meaningful synthetic data")

    rows: list[dict[str, str]] = []

    # --- Stable core (~70) ---
    for i in range(1, 71):
        person = f"C{i:03d}"
        rate = 0.88 + (i % 7) * 0.01
        # A few core members go quiet recently (absence watchlist)
        absent_recent = i in {3, 11, 19, 27}
        # A few decline but still show sometimes
        declining = i in {5, 15, 25, 35}
        for wi, week in enumerate(weeks):
            p = rate
            if week.month == 12 and week.day >= 20:
                p *= 0.75
            if week.month == 1 and week.day <= 7:
                p *= 0.85
            if absent_recent and wi >= n_weeks - 4:
                p = 0.0
            if declining and wi >= n_weeks - 12:
                p = max(0.15, rate - 0.45)
            # Broken streak candidates: solid run then miss latest
            if i in {7, 17, 37} and wi == n_weeks - 1:
                p = 0.0
            if i in {7, 17, 37} and n_weeks - 8 <= wi < n_weeks - 1:
                p = 0.98
            if random.random() < p:
                add_attendance(rows, person, week)

    # --- Mid-frequency pool ---
    for i in range(1, 51):
        person = f"M{i:03d}"
        rate = 0.32 + (i % 9) * 0.02
        for wi, week in enumerate(weeks):
            p = rate
            if person.endswith(("2", "5")) and wi >= n_weeks - 12:
                p = max(0.0, p - 0.15)
            if random.random() < p:
                add_attendance(rows, person, week)

    # --- Rare / fringe ---
    for i in range(1, 61):
        person = f"R{i:03d}"
        rate = 0.06 + (i % 8) * 0.015
        for week in weeks:
            if random.random() < rate:
                add_attendance(rows, person, week)

    # --- Returnees: history, long gap, then recent return ---
    for i in range(1, 9):
        person = f"RET{i:03d}"
        # early period attendance
        for week in weeks[:20]:
            if random.random() < 0.55:
                add_attendance(rows, person, week)
        # recent return (last 1–2 weeks)
        add_attendance(rows, person, weeks[-1])
        if i % 2 == 0:
            add_attendance(rows, person, weeks[-2])

    # --- New and persistent (first seen in last ~10 weeks, sticky) ---
    for i in range(1, 13):
        person = f"NS{i:03d}"
        first_idx = n_weeks - 10 + (i % 5)
        for wi in range(first_idx, n_weeks):
            # high early rate
            if random.random() < 0.75 or wi >= n_weeks - 3:
                add_attendance(rows, person, weeks[wi])

    # --- New but fading (few early hits, then silence) ---
    for i in range(1, 11):
        person = f"NF{i:03d}"
        first_idx = n_weeks - 11 + (i % 4)
        hits = 1 + (i % 2)
        for wi in range(first_idx, min(first_idx + hits, n_weeks - 3)):
            add_attendance(rows, person, weeks[wi])

    # --- Emerging regulars (tenure 10–20 weeks, strong recent) ---
    for i in range(1, 11):
        person = f"ER{i:03d}"
        first_idx = n_weeks - 18 + (i % 6)
        for wi in range(first_idx, n_weeks):
            if random.random() < 0.7:
                add_attendance(rows, person, week := weeks[wi])

    df = (
        pl.DataFrame(rows)
        .unique(subset=["week", "person"])
        .sort(["week", "person"])
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(OUT)

    weekly = df.group_by("week").len().sort("week")
    n_people = df["person"].n_unique()
    n = df["week"].n_unique()
    rates = (
        df.group_by("person")
        .len()
        .with_columns((pl.col("len") / n).alias("rate"))
    )
    core60 = rates.filter(pl.col("rate") >= 0.6).height

    print(f"wrote {OUT}")
    print(f"  date range : {weeks[0]} → {weeks[-1]} ({n_weeks} Sundays)")
    print(f"  rows       : {df.height}")
    print(f"  people     : {n_people}")
    print(
        f"  weekly     : mean={weekly['len'].mean():.1f} "
        f"median={weekly['len'].median():.1f} "
        f"min={weekly['len'].min()} max={weekly['len'].max()}"
    )
    print(f"  core ≥0.6  : {core60} people")


if __name__ == "__main__":
    main()
