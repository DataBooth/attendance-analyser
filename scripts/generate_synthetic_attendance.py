"""Generate long-format synthetic weekly attendance data.

Target shape:
- Sundays from first Sunday on/after 2025-01-01 through last Sunday on/before today
- Weekly headcount rises from ~100 at mid-2025 to ~140 by the latest Sunday
- Week-to-week change never exceeds 15 people (non-monotonic noise allowed)
- Stable core ~70 and life-cycle patterns for care-pack demos
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "synthetic_attendance.csv"

MAX_WEEK_DELTA = 15
MID_2025_TARGET = 100
END_TARGET = 140
START_TARGET = 92


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


def build_target_counts(weeks: list[date]) -> list[int]:
    """Smooth growth from early ~92 → mid-2025 ~100 → latest ~140.

    Adds modest noise, then enforces |Δ| ≤ MAX_WEEK_DELTA between successive weeks.
    """
    mid_anchor = date(2025, 7, 1)
    mid_idx = min(
        range(len(weeks)),
        key=lambda i: abs((weeks[i] - mid_anchor).days),
    )
    n = len(weeks)
    raw: list[float] = []
    for i, week in enumerate(weeks):
        if i <= mid_idx:
            # ease from START_TARGET to MID_2025_TARGET
            t = i / max(mid_idx, 1)
            base = START_TARGET + (MID_2025_TARGET - START_TARGET) * t
        else:
            t = (i - mid_idx) / max(n - 1 - mid_idx, 1)
            # ease-in toward end target
            eased = t * t * (3 - 2 * t)
            base = MID_2025_TARGET + (END_TARGET - MID_2025_TARGET) * eased
        # mild seasonal dips (Christmas / New Year)
        if week.month == 12 and week.day >= 20:
            base -= 8
        if week.month == 1 and week.day <= 7:
            base -= 5
        # non-monotonic noise
        base += random.uniform(-6, 6)
        # gentle sine wobble
        base += 3 * math.sin(i / 3.5)
        raw.append(base)

    # Enforce successive delta cap while tracking the intended level
    targets: list[int] = []
    prev: int | None = None
    for i, value in enumerate(raw):
        desired = int(round(value))
        if prev is None:
            count = desired
        else:
            lo = prev - MAX_WEEK_DELTA
            hi = prev + MAX_WEEK_DELTA
            count = max(lo, min(hi, desired))
            # pull slightly toward long-run target so we still reach ~140
            if i == n - 1:
                count = max(lo, min(hi, END_TARGET + random.randint(-3, 3)))
        targets.append(count)
        prev = count

    # If the end is still short of ~140 because of the delta cap, walk backward
    # adjustments are not needed if the path is long enough; nudge forward path
    if targets[-1] < END_TARGET - 5:
        deficit = END_TARGET - targets[-1]
        # distribute extra growth over the last third without breaking the cap
        start_i = max(mid_idx, n * 2 // 3)
        for i in range(start_i, n):
            room = MAX_WEEK_DELTA - abs(targets[i] - targets[i - 1]) if i else MAX_WEEK_DELTA
            bump = min(room, max(1, deficit // max(n - i, 1)))
            if i and targets[i] + bump - targets[i - 1] > MAX_WEEK_DELTA:
                bump = MAX_WEEK_DELTA - (targets[i] - targets[i - 1])
            if bump > 0:
                targets[i] += bump
                deficit -= bump
        # final clamp pass
        for i in range(1, n):
            d = targets[i] - targets[i - 1]
            if d > MAX_WEEK_DELTA:
                targets[i] = targets[i - 1] + MAX_WEEK_DELTA
            elif d < -MAX_WEEK_DELTA:
                targets[i] = targets[i - 1] - MAX_WEEK_DELTA

    return targets


def main(today: date | None = None) -> None:
    random.seed(42)
    today = today or date.today()

    start = first_sunday_on_or_after(date(2025, 1, 1))
    end = last_sunday_on_or_before(today)
    weeks = sunday_weeks(start, end)
    n_weeks = len(weeks)
    if n_weeks < 20:
        raise ValueError("Need a longer date range for meaningful synthetic data")

    targets = build_target_counts(weeks)

    # person -> priority weight for filling weekly quotas (higher = more core)
    priority: dict[str, float] = {}
    # person -> set of weeks they "want" to attend (base pattern)
    desired: dict[str, set[date]] = {}

    def ensure(person: str) -> None:
        desired.setdefault(person, set())

    def want(person: str, week: date, p: float) -> None:
        ensure(person)
        if random.random() < p:
            desired[person].add(week)

    # --- Stable core (~70 high-priority) ---
    for i in range(1, 71):
        person = f"C{i:03d}"
        priority[person] = 100 + i
        rate = 0.90 + (i % 7) * 0.008
        absent_recent = i in {3, 11, 19, 27}
        declining = i in {5, 15, 25, 35}
        for wi, week in enumerate(weeks):
            p = rate
            if week.month == 12 and week.day >= 20:
                p *= 0.8
            if week.month == 1 and week.day <= 7:
                p *= 0.88
            if absent_recent and wi >= n_weeks - 4:
                p = 0.0
            if declining and wi >= n_weeks - 12:
                p = max(0.2, rate - 0.4)
            if i in {7, 17, 37} and wi == n_weeks - 1:
                p = 0.0
            if i in {7, 17, 37} and n_weeks - 8 <= wi < n_weeks - 1:
                p = 0.98
            want(person, week, p)

    # --- Mid-frequency pool ---
    for i in range(1, 81):
        person = f"M{i:03d}"
        priority[person] = 40 + (i % 20)
        rate = 0.35 + (i % 9) * 0.02
        for wi, week in enumerate(weeks):
            p = rate
            # gradual lift in mid engagement as community grows
            p += 0.12 * (wi / max(n_weeks - 1, 1))
            if person.endswith(("2", "5")) and wi >= n_weeks - 12:
                p = max(0.05, p - 0.12)
            want(person, week, min(0.85, p))

    # --- Growth cohort: unlock over time to supply rising headcount ---
    for i in range(1, 121):
        person = f"G{i:03d}"
        priority[person] = 20 + (i % 15)
        # staggered first-seen across the series (more joiners later)
        first_idx = int((i / 121) ** 0.7 * (n_weeks - 5))
        rate = 0.45 + (i % 10) * 0.03
        for wi in range(first_idx, n_weeks):
            progress = (wi - first_idx) / max(n_weeks - first_idx, 1)
            p = rate * (0.55 + 0.45 * progress)
            want(person, week := weeks[wi], min(0.9, p))

    # --- Rare / fringe (flexible filler / trimmer) ---
    for i in range(1, 101):
        person = f"R{i:03d}"
        priority[person] = 5 + (i % 10)
        rate = 0.08 + (i % 8) * 0.02
        for wi, week in enumerate(weeks):
            p = rate + 0.1 * (wi / max(n_weeks - 1, 1))
            want(person, week, min(0.5, p))

    # --- Returnees ---
    for i in range(1, 9):
        person = f"RET{i:03d}"
        priority[person] = 30
        ensure(person)
        for week in weeks[:20]:
            if random.random() < 0.55:
                desired[person].add(week)
        desired[person].add(weeks[-1])
        if i % 2 == 0:
            desired[person].add(weeks[-2])

    # --- New and persistent ---
    for i in range(1, 16):
        person = f"NS{i:03d}"
        priority[person] = 55
        first_idx = n_weeks - 10 + (i % 5)
        for wi in range(first_idx, n_weeks):
            want(person, weeks[wi], 0.8 if wi < n_weeks - 3 else 0.95)

    # --- New but fading ---
    for i in range(1, 12):
        person = f"NF{i:03d}"
        priority[person] = 25
        first_idx = n_weeks - 11 + (i % 4)
        hits = 1 + (i % 2)
        for wi in range(first_idx, min(first_idx + hits, n_weeks - 3)):
            desired.setdefault(person, set()).add(weeks[wi])

    # --- Emerging regulars ---
    for i in range(1, 14):
        person = f"ER{i:03d}"
        priority[person] = 60
        first_idx = n_weeks - 18 + (i % 6)
        for wi in range(first_idx, n_weeks):
            want(person, weeks[wi], 0.72)

    # Build per-week sets from desires
    by_week: dict[date, set[str]] = {w: set() for w in weeks}
    for person, week_set in desired.items():
        for week in week_set:
            by_week[week].add(person)

    all_people = sorted(priority.keys(), key=lambda p: priority[p], reverse=True)

    # Reconcile each week to the target headcount
    for wi, week in enumerate(weeks):
        target = targets[wi]
        present = by_week[week]
        # candidates not present, prefer lower priority for adds that are "growth"
        absent = [p for p in all_people if p not in present]

        # Remove extras: drop lowest-priority first (keep core)
        if len(present) > target:
            ordered = sorted(present, key=lambda p: priority.get(p, 0))
            for person in ordered:
                if len(present) <= target:
                    break
                # protect strong care-pack labels somewhat
                if person.startswith(("NS", "ER", "C")) and random.random() < 0.7:
                    continue
                present.discard(person)

        # Add missing: highest-priority absentees first, then random fringe
        if len(present) < target:
            ordered_add = sorted(
                absent, key=lambda p: priority.get(p, 0), reverse=True
            )
            for person in ordered_add:
                if len(present) >= target:
                    break
                present.add(person)

        # If still short, mint one-off visitors
        k = 1
        while len(present) < target:
            person = f"V{wi:03d}_{k:03d}"
            priority[person] = 1
            present.add(person)
            k += 1

        by_week[week] = present

    # Second pass: enforce week-to-week delta ≤ 15 by trimming/adding toward previous
    for wi in range(1, n_weeks):
        prev = by_week[weeks[wi - 1]]
        cur = by_week[weeks[wi]]
        diff = len(cur) - len(prev)
        if diff > MAX_WEEK_DELTA:
            excess = diff - MAX_WEEK_DELTA
            ordered = sorted(cur, key=lambda p: priority.get(p, 0))
            for person in ordered:
                if excess <= 0:
                    break
                if person.startswith("C") and random.random() < 0.85:
                    continue
                cur.discard(person)
                excess -= 1
        elif diff < -MAX_WEEK_DELTA:
            need = -MAX_WEEK_DELTA - diff
            candidates = sorted(
                (p for p in all_people if p not in cur),
                key=lambda p: priority.get(p, 0),
                reverse=True,
            )
            for person in candidates:
                if need <= 0:
                    break
                cur.add(person)
                need -= 1
            k = 1
            while need > 0:
                person = f"V{wi:03d}x{k:03d}"
                priority[person] = 1
                cur.add(person)
                need -= 1
                k += 1
        by_week[weeks[wi]] = cur

    rows: list[dict[str, str]] = []
    for week in weeks:
        for person in sorted(by_week[week]):
            rows.append({"week": week.isoformat(), "person": person})

    df = pl.DataFrame(rows).sort(["week", "person"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(OUT)

    weekly = df.group_by("week").len().sort("week")
    counts = weekly["len"].to_list()
    deltas = [abs(counts[i] - counts[i - 1]) for i in range(1, len(counts))]
    mid_idx = min(
        range(len(weeks)),
        key=lambda i: abs((weeks[i] - date(2025, 7, 1)).days),
    )
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
    print(
        f"  mid-2025   : {weeks[mid_idx]} → {counts[mid_idx]} people "
        f"(target ~{MID_2025_TARGET})"
    )
    print(f"  latest     : {weeks[-1]} → {counts[-1]} people (target ~{END_TARGET})")
    print(f"  max |Δ week|: {max(deltas) if deltas else 0} (cap {MAX_WEEK_DELTA})")
    print(f"  core ≥0.6  : {core60} people")


if __name__ == "__main__":
    main()
