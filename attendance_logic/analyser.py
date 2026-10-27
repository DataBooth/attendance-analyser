"""Pure attendance analysis against an in-memory DuckDB table.

Note: in-memory anonymisation (stable token mapping of person IDs) can be
added later without changing the public methods.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import polars as pl


class AttendanceAnalyser:
    """Encapsulates attendance metrics and pastoral shortlists."""

    def __init__(self, csv_path: str | Path, table: str = "attendance"):
        self.con = duckdb.connect(":memory:")
        self.table = table
        self._load(csv_path)

    def _load(self, csv_path: str | Path) -> None:
        path = Path(csv_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Attendance CSV not found: {path}")
        path_str = path.as_posix()
        self.con.execute(
            f"""
            CREATE TABLE {self.table} AS
            SELECT
                week::DATE AS week,
                person::VARCHAR AS person,
                1 AS attended
            FROM read_csv_auto('{path_str}')
            """
        )

    def _query(self, sql: str, params: Optional[list] = None) -> pl.DataFrame:
        """Run SQL and return a Polars DataFrame (DuckDB 2.x compatible)."""
        if params is None:
            return pl.from_pandas(self.con.execute(sql).fetchdf())
        return pl.from_pandas(self.con.execute(sql, params).fetchdf())

    def n_weeks(self) -> int:
        row = self.con.execute(
            f"SELECT COUNT(DISTINCT week) FROM {self.table}"
        ).fetchone()
        return int(row[0])

    def max_week(self) -> object:
        row = self.con.execute(
            f"SELECT MAX(week) FROM {self.table}"
        ).fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Core metrics
    # ------------------------------------------------------------------
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
        people = (
            rates.filter(pl.col("attendance_rate") >= min_rate)["person"]
            .to_list()
        )
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
        """Consecutive-week attendee overlap metrics."""
        return self._query(
            f"""
            WITH weeks AS (
                SELECT DISTINCT week FROM {self.table}
            ),
            ordered AS (
                SELECT
                    week,
                    LAG(week) OVER (ORDER BY week) AS prev_week
                FROM weeks
            ),
            pairs AS (
                SELECT week, prev_week
                FROM ordered
                WHERE prev_week IS NOT NULL
            ),
            shared AS (
                SELECT
                    p.week,
                    p.prev_week,
                    COUNT(*) AS shared
                FROM pairs p
                JOIN {self.table} curr ON curr.week = p.week
                JOIN {self.table} prev
                  ON prev.week = p.prev_week
                 AND prev.person = curr.person
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

    # ------------------------------------------------------------------
    # Person timeline (foundation for care lists)
    # ------------------------------------------------------------------
    def person_timeline_summary(self, recent_weeks: int = 12) -> pl.DataFrame:
        """Per-person first/last seen, rates, streaks, and recent activity."""
        n = self.n_weeks()
        return self._query(
            f"""
            WITH bounds AS (
                SELECT MIN(week) AS min_week, MAX(week) AS max_week
                FROM {self.table}
            ),
            base AS (
                SELECT
                    a.person,
                    MIN(a.week) AS first_seen,
                    MAX(a.week) AS last_seen,
                    COUNT(*) AS weeks_attended,
                    COUNT(*) * 1.0 / {n} AS overall_rate
                FROM {self.table} a
                GROUP BY a.person
            ),
            recent AS (
                SELECT
                    a.person,
                    COUNT(*) AS recent_attended,
                    COUNT(*) * 1.0 / {recent_weeks} AS recent_rate
                FROM {self.table} a, bounds b
                WHERE a.week > b.max_week - INTERVAL '{recent_weeks} weeks'
                GROUP BY a.person
            ),
            numbered AS (
                SELECT
                    person,
                    week,
                    ROW_NUMBER() OVER (
                        PARTITION BY person ORDER BY week
                    ) AS rn
                FROM {self.table}
            ),
            streak_groups AS (
                SELECT
                    person,
                    week,
                    week - (rn - 1) * INTERVAL '7 days' AS grp
                FROM numbered
            ),
            streaks AS (
                SELECT
                    person,
                    grp,
                    COUNT(*) AS streak_len,
                    MIN(week) AS streak_start,
                    MAX(week) AS streak_end
                FROM streak_groups
                GROUP BY person, grp
            ),
            streak_stats AS (
                SELECT
                    person,
                    MAX(streak_len) AS longest_streak,
                    MAX(streak_len) FILTER (
                        WHERE streak_end = (
                            SELECT MAX(s2.streak_end)
                            FROM streaks s2
                            WHERE s2.person = streaks.person
                        )
                    ) AS streak_at_last_seen
                FROM streaks
                GROUP BY person
            ),
            present_latest AS (
                SELECT DISTINCT person
                FROM {self.table}, bounds
                WHERE week = max_week
            )
            SELECT
                b.person,
                b.first_seen,
                b.last_seen,
                b.weeks_attended,
                b.overall_rate,
                COALESCE(r.recent_attended, 0) AS recent_attended,
                COALESCE(r.recent_rate, 0) AS recent_rate,
                COALESCE(r.recent_rate, 0) - b.overall_rate AS delta,
                date_diff('week', b.last_seen, bounds.max_week)
                    AS weeks_since_last,
                date_diff('week', b.first_seen, bounds.max_week)
                    AS tenure_weeks,
                date_diff('week', b.first_seen, b.last_seen) + 1
                    AS span_weeks,
                b.weeks_attended * 1.0
                    / NULLIF(date_diff('week', b.first_seen, bounds.max_week) + 1, 0)
                    AS rate_since_first,
                COALESCE(ss.longest_streak, 1) AS longest_streak,
                COALESCE(ss.streak_at_last_seen, 1) AS streak_at_last_seen,
                CASE WHEN pl.person IS NOT NULL THEN TRUE ELSE FALSE END
                    AS present_latest_week,
                bounds.max_week AS as_of_week
            FROM base b
            CROSS JOIN bounds
            LEFT JOIN recent r USING (person)
            LEFT JOIN streak_stats ss USING (person)
            LEFT JOIN present_latest pl USING (person)
            ORDER BY b.overall_rate DESC, b.person
            """
        )

    # ------------------------------------------------------------------
    # Follow-up shortlists
    # ------------------------------------------------------------------
    def absence_watchlist(
        self,
        min_overall: float = 0.5,
        min_weeks_away: int = 2,
        recent_weeks: int = 12,
    ) -> pl.DataFrame:
        """Historically regular people who have gone quiet."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        out = t.filter(
            (pl.col("overall_rate") >= min_overall)
            & (pl.col("weeks_since_last") >= min_weeks_away)
        ).with_columns(
            pl.lit("Absence after reliability").alias("reason"),
            pl.lit("Gentle check-in").alias("suggested_action"),
            (
                pl.col("weeks_since_last") * 2.0
                + pl.col("overall_rate") * 5.0
                + pl.col("longest_streak") * 0.3
            ).alias("priority_score"),
        )
        return out.sort("priority_score", descending=True)

    def decline_watchlist(
        self,
        recent_weeks: int = 12,
        max_delta: float = -0.2,
        min_history_weeks: int = 8,
        min_overall: float = 0.25,
        exclude_fully_absent: bool = True,
        min_weeks_away_for_absent: int = 2,
    ) -> pl.DataFrame:
        """People still in view but with a sharp recent decline."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        filt = (
            (pl.col("delta") <= max_delta)
            & (pl.col("tenure_weeks") >= min_history_weeks)
            & (pl.col("overall_rate") >= min_overall)
        )
        if exclude_fully_absent:
            filt = filt & (
                pl.col("weeks_since_last") < min_weeks_away_for_absent
            )
        out = t.filter(filt).with_columns(
            pl.lit("Sharp recent decline").alias("reason"),
            pl.lit("Light-touch check-in").alias("suggested_action"),
            (
                pl.col("delta").abs() * 8.0
                + pl.col("overall_rate") * 3.0
                + pl.col("tenure_weeks") * 0.05
            ).alias("priority_score"),
        )
        return out.sort("priority_score", descending=True)

    def broken_streak_watchlist(
        self,
        min_streak: int = 4,
        recent_weeks: int = 12,
        min_weeks_away: int = 1,
    ) -> pl.DataFrame:
        """People who broke a meaningful consecutive-attendance streak."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        out = t.filter(
            (pl.col("streak_at_last_seen") >= min_streak)
            & (pl.col("weeks_since_last") >= min_weeks_away)
        ).with_columns(
            pl.lit("Broken attendance streak").alias("reason"),
            pl.lit("Timely, specific check-in").alias("suggested_action"),
            (
                pl.col("streak_at_last_seen") * 1.5
                + pl.col("weeks_since_last") * 2.0
                + pl.col("overall_rate") * 3.0
            ).alias("priority_score"),
        )
        return out.sort("priority_score", descending=True)

    def returnee_watchlist(
        self,
        min_gap_weeks: int = 8,
        recent_window: int = 2,
        recent_weeks: int = 12,
    ) -> pl.DataFrame:
        """People back after a long gap (re-welcome, not first-timer)."""
        # Gap before latest burst: approximate via SQL on last stretch
        df = self._query(
            f"""
            WITH bounds AS (
                SELECT MAX(week) AS max_week FROM {self.table}
            ),
            last_touch AS (
                SELECT person, MAX(week) AS last_seen
                FROM {self.table}
                GROUP BY person
            ),
            recent_hits AS (
                SELECT a.person, COUNT(*) AS hits_recent
                FROM {self.table} a, bounds b
                WHERE a.week > b.max_week - INTERVAL '{recent_window} weeks'
                GROUP BY a.person
            ),
            prior AS (
                SELECT
                    a.person,
                    MAX(a.week) AS last_before_recent
                FROM {self.table} a, bounds b
                WHERE a.week <= b.max_week - INTERVAL '{recent_window} weeks'
                GROUP BY a.person
            )
            SELECT
                lt.person,
                lt.last_seen,
                p.last_before_recent,
                date_diff('week', p.last_before_recent, lt.last_seen)
                    AS gap_weeks,
                COALESCE(rh.hits_recent, 0) AS hits_recent,
                b.max_week AS as_of_week
            FROM last_touch lt
            CROSS JOIN bounds b
            JOIN prior p USING (person)
            LEFT JOIN recent_hits rh USING (person)
            WHERE COALESCE(rh.hits_recent, 0) >= 1
              AND date_diff('week', p.last_before_recent, lt.last_seen)
                  >= {min_gap_weeks}
            ORDER BY gap_weeks DESC
            """
        )
        if df.height == 0:
            return df.with_columns(
                pl.lit(None, dtype=pl.Utf8).alias("reason"),
                pl.lit(None, dtype=pl.Utf8).alias("suggested_action"),
                pl.lit(None, dtype=pl.Float64).alias("priority_score"),
            )
        timeline = self.person_timeline_summary(recent_weeks=recent_weeks)
        out = df.join(
            timeline.select(
                [
                    "person",
                    "first_seen",
                    "overall_rate",
                    "weeks_attended",
                    "longest_streak",
                ]
            ),
            on="person",
            how="left",
        ).with_columns(
            pl.lit("Return after long gap").alias("reason"),
            pl.lit("Warm re-welcome").alias("suggested_action"),
            (
                pl.col("gap_weeks") * 0.5
                + pl.col("hits_recent") * 2.0
                + pl.col("overall_rate").fill_null(0) * 2.0
            ).alias("priority_score"),
        )
        return out.sort("priority_score", descending=True)

    # ------------------------------------------------------------------
    # New / connect-in shortlists
    # ------------------------------------------------------------------
    def newcomers(
        self, within_weeks: int = 12, recent_weeks: int = 12
    ) -> pl.DataFrame:
        """People whose first attendance falls in the recent window."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        return t.filter(pl.col("tenure_weeks") <= within_weeks).sort(
            ["first_seen", "person"], descending=[True, False]
        )

    def new_and_persistent(
        self,
        within_weeks: int = 12,
        min_attendances: int = 3,
        min_early_rate: float = 0.45,
        min_recent_hits: int = 2,
        recent_hit_window: int = 4,
        recent_weeks: int = 12,
    ) -> pl.DataFrame:
        """New people who are forming a habit — connect them in."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        recent_hits = self._query(
            f"""
            WITH bounds AS (SELECT MAX(week) AS max_week FROM {self.table})
            SELECT a.person, COUNT(*) AS hits_last_window
            FROM {self.table} a, bounds b
            WHERE a.week > b.max_week - INTERVAL '{recent_hit_window} weeks'
            GROUP BY a.person
            """
        )
        out = (
            t.join(recent_hits, on="person", how="left")
            .with_columns(pl.col("hits_last_window").fill_null(0))
            .filter(
                (pl.col("tenure_weeks") <= within_weeks)
                & (
                    (pl.col("weeks_attended") >= min_attendances)
                    | (pl.col("rate_since_first") >= min_early_rate)
                )
                & (pl.col("hits_last_window") >= min_recent_hits)
            )
            .with_columns(
                pl.lit("New and persistent").alias("reason"),
                pl.lit("Connect into community").alias("suggested_action"),
                (
                    pl.col("rate_since_first") * 6.0
                    + pl.col("hits_last_window") * 2.0
                    + pl.col("weeks_attended") * 0.5
                ).alias("priority_score"),
            )
        )
        return out.sort("priority_score", descending=True)

    def new_and_fading(
        self,
        within_weeks: int = 12,
        max_attendances: int = 3,
        min_weeks_away: int = 2,
        recent_weeks: int = 12,
    ) -> pl.DataFrame:
        """Recent first-timers who have gone quiet — early follow-up."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        out = t.filter(
            (pl.col("tenure_weeks") <= within_weeks)
            & (pl.col("weeks_attended") <= max_attendances)
            & (pl.col("weeks_since_last") >= min_weeks_away)
        ).with_columns(
            pl.lit("New but fading").alias("reason"),
            pl.lit("Early hospitality follow-up").alias("suggested_action"),
            (
                pl.col("weeks_since_last") * 2.0
                + (max_attendances - pl.col("weeks_attended")) * 1.5
                + pl.col("rate_since_first").fill_null(0) * 2.0
            ).alias("priority_score"),
        )
        return out.sort("priority_score", descending=True)

    def emerging_regulars(
        self,
        min_tenure_weeks: int = 8,
        max_tenure_weeks: int = 26,
        min_rate_since_first: float = 0.5,
        min_recent_rate: float = 0.5,
        recent_weeks: int = 12,
    ) -> pl.DataFrame:
        """Past the brand-new window; sustained pattern — invite deeper."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        out = t.filter(
            (pl.col("tenure_weeks") >= min_tenure_weeks)
            & (pl.col("tenure_weeks") <= max_tenure_weeks)
            & (pl.col("rate_since_first") >= min_rate_since_first)
            & (pl.col("recent_rate") >= min_recent_rate)
        ).with_columns(
            pl.lit("Emerging regular").alias("reason"),
            pl.lit("Thank and invite deeper").alias("suggested_action"),
            (
                pl.col("recent_rate") * 5.0
                + pl.col("rate_since_first") * 3.0
                + pl.col("longest_streak") * 0.2
            ).alias("priority_score"),
        )
        return out.sort("priority_score", descending=True)

    def second_visit_funnel(self, return_within_weeks: int = 4) -> pl.DataFrame:
        """Cohort funnel: first visit → returned → sticky at 8 weeks."""
        return self._query(
            f"""
            WITH firsts AS (
                SELECT person, MIN(week) AS first_seen
                FROM {self.table}
                GROUP BY person
            ),
            second AS (
                SELECT
                    f.person,
                    f.first_seen,
                    MIN(a.week) AS second_seen
                FROM firsts f
                JOIN {self.table} a
                  ON a.person = f.person AND a.week > f.first_seen
                GROUP BY f.person, f.first_seen
            ),
            early_counts AS (
                SELECT
                    f.person,
                    f.first_seen,
                    COUNT(*) AS attendances_first_8w
                FROM firsts f
                JOIN {self.table} a
                  ON a.person = f.person
                 AND a.week >= f.first_seen
                 AND a.week < f.first_seen + INTERVAL '8 weeks'
                GROUP BY f.person, f.first_seen
            ),
            bounds AS (
                SELECT MAX(week) AS max_week FROM {self.table}
            )
            SELECT
                f.first_seen AS cohort_week,
                COUNT(*) AS first_visits,
                COUNT(*) FILTER (
                    WHERE s.second_seen IS NOT NULL
                      AND date_diff('week', f.first_seen, s.second_seen)
                          <= {return_within_weeks}
                ) AS returned_within_window,
                COUNT(*) FILTER (
                    WHERE COALESCE(ec.attendances_first_8w, 1) >= 4
                ) AS sticky_at_8w,
                COUNT(*) FILTER (
                    WHERE s.second_seen IS NOT NULL
                      AND date_diff('week', f.first_seen, s.second_seen)
                          <= {return_within_weeks}
                ) * 1.0 / COUNT(*) AS return_rate,
                COUNT(*) FILTER (
                    WHERE COALESCE(ec.attendances_first_8w, 1) >= 4
                ) * 1.0 / COUNT(*) AS sticky_rate
            FROM firsts f
            CROSS JOIN bounds b
            LEFT JOIN second s USING (person)
            LEFT JOIN early_counts ec USING (person)
            -- only cohorts old enough to measure 8-week stickiness
            WHERE f.first_seen <= b.max_week - INTERVAL '8 weeks'
            GROUP BY f.first_seen
            ORDER BY f.first_seen
            """
        )

    def care_pack(
        self,
        core_threshold: float = 0.6,
        recent_weeks: int = 12,
        min_weeks_away: int = 2,
        new_within_weeks: int = 12,
        top_n: int = 15,
    ) -> dict[str, pl.DataFrame]:
        """Bundle shortlists leaders can act on this week."""
        absence = self.absence_watchlist(
            min_overall=max(0.45, core_threshold - 0.1),
            min_weeks_away=min_weeks_away,
            recent_weeks=recent_weeks,
        )
        decline = self.decline_watchlist(
            recent_weeks=recent_weeks,
            max_delta=-0.2,
            min_history_weeks=8,
            min_overall=0.25,
            min_weeks_away_for_absent=min_weeks_away,
        )
        broken = self.broken_streak_watchlist(
            min_streak=4,
            recent_weeks=recent_weeks,
            min_weeks_away=1,
        )
        returnees = self.returnee_watchlist(
            min_gap_weeks=8,
            recent_window=2,
            recent_weeks=recent_weeks,
        )
        sticky = self.new_and_persistent(
            within_weeks=new_within_weeks,
            recent_weeks=recent_weeks,
        )
        fading = self.new_and_fading(
            within_weeks=new_within_weeks,
            recent_weeks=recent_weeks,
            min_weeks_away=min_weeks_away,
        )
        emerging = self.emerging_regulars(
            recent_weeks=recent_weeks,
            min_rate_since_first=max(0.45, core_threshold - 0.1),
        )
        funnel = self.second_visit_funnel()

        def head(df: pl.DataFrame) -> pl.DataFrame:
            return df.head(top_n) if df.height else df

        return {
            "absence": head(absence),
            "decline": head(decline),
            "broken_streak": head(broken),
            "returnees": head(returnees),
            "new_persistent": head(sticky),
            "new_fading": head(fading),
            "emerging_regulars": head(emerging),
            "funnel": funnel,
            "timeline": self.person_timeline_summary(recent_weeks=recent_weeks),
        }

    def add_service_filter(self, service_type: Optional[str] = None) -> None:
        """Placeholder for when the source table has service_type etc."""
        pass
