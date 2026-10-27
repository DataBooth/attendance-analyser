"""Smoke-test AttendanceAnalyser without launching the Marimo UI."""

from __future__ import annotations

from pathlib import Path

from attendance_logic import AttendanceAnalyser

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    csv_path = ROOT / "artifacts" / "synthetic_attendance.csv"
    away_path = ROOT / "artifacts" / "synthetic_away_intervals.csv"

    analyser = AttendanceAnalyser(csv_path, away_csv=away_path)
    assert analyser.n_weeks() > 0
    assert analyser.has_away_data
    assert analyser.away_intervals().height >= 1

    rates = analyser.attendance_rates()
    assert {"person", "weeks_attended", "attendance_rate"} <= set(rates.columns)

    core = analyser.core_group(0.6)
    weekly = analyser.weekly_totals(0.6)
    assert {"week", "total_attendees", "core_present"} <= set(weekly.columns)

    heat = analyser.heatmap_data(0.25)
    assert heat.height >= 0

    recency = analyser.recency_comparison(12)
    assert {"person", "overall_rate", "recent_rate", "delta"} <= set(
        recency.columns
    )

    overlap = analyser.week_on_week_overlap()
    assert overlap.height == analyser.n_weeks() - 1

    timeline = analyser.person_timeline_summary()
    assert {
        "person",
        "first_seen",
        "last_seen",
        "weeks_since_last",
        "weeks_since_last_unexplained",
        "known_away_now",
        "longest_streak",
        "rate_since_first",
    } <= set(timeline.columns)

    # Excused core leave: calendar gap but unexplained clock paused
    c003 = timeline.filter(timeline["person"] == "C003")
    assert c003.height == 1
    assert int(c003["weeks_since_last"][0]) >= 2
    assert int(c003["weeks_since_last_unexplained"][0]) == 0
    assert bool(c003["known_away_now"][0]) is True

    # Unexplained quiet core person remains on the clock
    c027 = timeline.filter(timeline["person"] == "C027")
    assert c027.height == 1
    assert int(c027["weeks_since_last_unexplained"][0]) >= 2

    pack_on = analyser.care_pack(respect_away=True)
    pack_off = analyser.care_pack(respect_away=False)
    for key in [
        "absence",
        "decline",
        "broken_streak",
        "returnees",
        "new_persistent",
        "new_fading",
        "emerging_regulars",
        "funnel",
        "timeline",
        "away_intervals",
    ]:
        assert key in pack_on

    abs_on = set(pack_on["absence"]["person"].to_list()) if pack_on["absence"].height else set()
    abs_off = set(pack_off["absence"]["person"].to_list()) if pack_off["absence"].height else set()
    assert "C003" not in abs_on
    assert "C003" in abs_off
    assert "C027" in abs_on

    assert pack_on["absence"].height >= 1
    assert pack_on["new_persistent"].height >= 1
    assert pack_on["funnel"].height >= 1
    assert pack_on["away_intervals"].height >= 1

    # Attendance-only still works
    bare = AttendanceAnalyser(csv_path)
    assert bare.has_away_data is False
    bare_pack = bare.care_pack(respect_away=True)
    assert bare_pack["absence"].height >= 1

    print(
        f"OK n_weeks={analyser.n_weeks()} people={rates.height} "
        f"core={core.height} "
        f"absence_on={pack_on['absence'].height} "
        f"absence_off={pack_off['absence'].height} "
        f"away_intervals={pack_on['away_intervals'].height} "
        f"suppressed_C003=yes unexplained_C027=yes"
    )


if __name__ == "__main__":
    main()
