"""Smoke-test AttendanceAnalyser without launching the Marimo UI."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

ROOT = Path(__file__).resolve().parents[1]


class AttendanceAnalyser:
    """Minimal mirror of the notebook class for headless smoke tests."""

    def __init__(self, csv_path: str | Path, table: str = "attendance"):
        self.con = duckdb.connect(":memory:")
        self.table = table
        path = Path(csv_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        path_str = path.as_posix()
        self.con.execute(
            f"""
            CREATE TABLE {self.table} AS
            SELECT week::DATE AS week, person, 1 AS attended
            FROM read_csv_auto('{path_str}')
            """
        )

    def _query(self, sql: str, params: list | None = None) -> pl.DataFrame:
        if params is None:
            return pl.from_pandas(self.con.execute(sql).fetchdf())
        return pl.from_pandas(self.con.execute(sql, params).fetchdf())

    def n_weeks(self) -> int:
        row = self.con.execute(
            f"SELECT COUNT(DISTINCT week) FROM {self.table}"
        ).fetchone()
        return int(row[0])

    def attendance_rates(self) -> pl.DataFrame:
        n = self.n_weeks()
        return self._query(
            f"""
            SELECT
                person,
                COUNT(*) AS weeks_attended,
                COUNT(*) * 1.0 / {n} AS attendance_rate
            FROM {self.table}
            GROUP BY person
            ORDER BY attendance_rate DESC
            """
        )

    def core_group(self, threshold: float) -> pl.DataFrame:
        return self.attendance_rates().filter(
            pl.col("attendance_rate") >= threshold
        )

    def weekly_totals(self, threshold: float) -> pl.DataFrame:
        n = self.n_weeks()
        return self._query(
            f"""
            WITH person_rates AS (
                SELECT person, COUNT(*) * 1.0 / {n} AS rate
                FROM {self.table}
                GROUP BY person
            )
            SELECT
                a.week,
                COUNT(*) AS total_attendees,
                COUNT(*) FILTER (WHERE pr.rate >= {threshold}) AS core_present
            FROM {self.table} a
            LEFT JOIN person_rates pr USING (person)
            GROUP BY a.week
            ORDER BY a.week
            """
        )

    def heatmap_data(self, min_rate: float = 0.25) -> pl.DataFrame:
        rates = self.attendance_rates()
        people = rates.filter(pl.col("attendance_rate") >= min_rate)[
            "person"
        ].to_list()
        if not people:
            return pl.DataFrame(
                schema={
                    "person": pl.Utf8,
                    "week": pl.Date,
                    "attended": pl.Int64,
                }
            )
        placeholders = ",".join("?" * len(people))
        return self._query(
            f"""
            SELECT person, week, attended
            FROM {self.table}
            WHERE person IN ({placeholders})
            ORDER BY person, week
            """,
            people,
        )

    def recency_comparison(
        self, recent_weeks: int, min_overall: float = 0.2
    ) -> pl.DataFrame:
        n = self.n_weeks()
        return self._query(
            f"""
            WITH overall AS (
                SELECT person, COUNT(*) * 1.0 / {n} AS overall_rate
                FROM {self.table}
                GROUP BY person
            ),
            recent_cutoff AS (
                SELECT MAX(week) - INTERVAL '{recent_weeks} weeks' AS cutoff
                FROM {self.table}
            ),
            recent AS (
                SELECT
                    person,
                    COUNT(*) * 1.0 / {recent_weeks} AS recent_rate
                FROM {self.table}, recent_cutoff
                WHERE week > cutoff
                GROUP BY person
            )
            SELECT
                o.person,
                o.overall_rate,
                COALESCE(r.recent_rate, 0) AS recent_rate,
                COALESCE(r.recent_rate, 0) - o.overall_rate AS delta
            FROM overall o
            LEFT JOIN recent r USING (person)
            WHERE o.overall_rate >= {min_overall}
            ORDER BY delta DESC
            """
        )

    def week_on_week_overlap(self) -> pl.DataFrame:
        return self._query(
            f"""
            WITH weeks AS (
                SELECT DISTINCT week FROM {self.table}
            ),
            ordered AS (
                SELECT week, LAG(week) OVER (ORDER BY week) AS prev_week
                FROM weeks
            ),
            pairs AS (
                SELECT week, prev_week FROM ordered WHERE prev_week IS NOT NULL
            ),
            shared AS (
                SELECT p.week, p.prev_week, COUNT(*) AS shared
                FROM pairs p
                JOIN {self.table} curr ON curr.week = p.week
                JOIN {self.table} prev
                  ON prev.week = p.prev_week AND prev.person = curr.person
                GROUP BY p.week, p.prev_week
            ),
            counts AS (
                SELECT week, COUNT(*) AS n FROM {self.table} GROUP BY week
            )
            SELECT
                p.prev_week,
                p.week,
                c_prev.n AS prev_count,
                c_curr.n AS curr_count,
                s.shared,
                c_curr.n - s.shared AS newcomers,
                c_prev.n - s.shared AS leavers,
                s.shared * 1.0 / c_prev.n AS retention,
                s.shared * 1.0 / (c_prev.n + c_curr.n - s.shared) AS jaccard
            FROM pairs p
            JOIN shared s USING (week, prev_week)
            JOIN counts c_prev ON c_prev.week = p.prev_week
            JOIN counts c_curr ON c_curr.week = p.week
            ORDER BY p.week
            """
        )


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
    assert {
        "prev_week",
        "week",
        "shared",
        "retention",
        "jaccard",
        "newcomers",
        "leavers",
    } <= set(overlap.columns)
    assert overlap.height == analyser.n_weeks() - 1
    print(
        f"OK n_weeks={analyser.n_weeks()} "
        f"people={rates.height} core={core.height} "
        f"weeks={weekly.height} heat_rows={heat.height} "
        f"recency={recency.height} "
        f"overlap_mean_retention={overlap['retention'].mean():.1%} "
        f"overlap_mean_jaccard={overlap['jaccard'].mean():.1%}"
    )


if __name__ == "__main__":
    main()
