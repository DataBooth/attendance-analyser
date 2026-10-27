"""Smoke-test AttendanceAnalyser without launching the Marimo UI."""

from __future__ import annotations

from pathlib import Path

from attendance_logic import AttendanceAnalyser

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    csv_path = ROOT / "artifacts" / "synthetic_attendance.csv"
    analyser = AttendanceAnalyser(csv_path)

    assert analyser.n_weeks() > 0
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
        "longest_streak",
        "rate_since_first",
    } <= set(timeline.columns)

    pack = analyser.care_pack()
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
    ]:
        assert key in pack

    # Synthetic fixture should exercise each pastoral list
    assert pack["absence"].height >= 1
    assert pack["decline"].height >= 1
    assert pack["new_persistent"].height >= 1
    assert pack["new_fading"].height >= 1
    assert pack["emerging_regulars"].height >= 1
    assert pack["funnel"].height >= 1

    print(
        f"OK n_weeks={analyser.n_weeks()} people={rates.height} "
        f"core={core.height} "
        f"absence={pack['absence'].height} "
        f"decline={pack['decline'].height} "
        f"sticky={pack['new_persistent'].height} "
        f"fading={pack['new_fading'].height} "
        f"emerging={pack['emerging_regulars'].height} "
        f"funnel_cohorts={pack['funnel'].height}"
    )


if __name__ == "__main__":
    main()
