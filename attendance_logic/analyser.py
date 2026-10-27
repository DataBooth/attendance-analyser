"""Pure attendance analysis against an in-memory DuckDB table.

Note: in-memory anonymisation (stable token mapping of person IDs) can be
added later without changing the public methods.

Phase 1 excused absence: optional away_intervals CSV pauses care clocks for
explained weeks (holiday, sick, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import polars as pl

AWAY_STATUSES = ("scheduled", "active", "completed")
SUPPRESS_REASONS_DEFAULT = True


class AttendanceAnalyser:
    """Encapsulates attendance metrics and pastoral shortlists."""

    def __init__(
        self,
        csv_path: str | Path,
        away_csv: str | Path | None = None,
        table: str = "attendance",
        away_table: str = "away_intervals",
    ):
        self.con = duckdb.connect(":memory:")
        self.table = table
        self.away_table = away_table
        self._load_attendance(csv_path)
        self._load_away(away_csv)
        self.has_away_data = self._away_row_count() > 0

    def _load_attendance(self, csv_path: str | Path) -> None:
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
        self.con.execute(
            f"""
            CREATE TABLE calendar AS
            SELECT DISTINCT week::DATE AS week
            FROM {self.table}
            ORDER BY 1
            """
        )

    def _load_away(self, away_csv: str | Path | None) -> None:
        """Load away intervals or create an empty compatible table."""
        schema_sql = f"""
            CREATE TABLE {self.away_table} (
                person VARCHAR,
                start_week DATE,
                end_week DATE,
                reason_code VARCHAR,
                status VARCHAR,
                suppress_care_alerts BOOLEAN,
                note VARCHAR,
                recorded_by VARCHAR,
                source VARCHAR
            )
        """
        if away_csv is None:
            self.con.execute(schema_sql)
            return

        path = Path(away_csv).expanduser().resolve()
        if not path.exists():
            self.con.execute(schema_sql)
            return

        path_str = path.as_posix()
        # Flexible load then normalise columns
        self.con.execute(
            f"""
            CREATE TABLE {self.away_table}_raw AS
            SELECT * FROM read_csv_auto('{path_str}', header=true)
            """
        )
        cols = {
            r[0].lower()
            for r in self.con.execute(
                f"DESCRIBE {self.away_table}_raw"
            ).fetchall()
        }

        def col(name: str, expr: str) -> str:
            return expr if name in cols else f"NULL AS {name}"

        # Map whatever casing read_csv produced
        raw_cols = {
            r[0]: r[0]
            for r in self.con.execute(
                f"DESCRIBE {self.away_table}_raw"
            ).fetchall()
        }
        lower_map = {k.lower(): k for k in raw_cols}

        def src(name: str) -> str:
            return f'"{lower_map[name]}"' if name in lower_map else "NULL"

        self.con.execute(
            f"""
            CREATE TABLE {self.away_table} AS
            SELECT
                {src('person')}::VARCHAR AS person,
                {src('start_week')}::DATE AS start_week,
                {src('end_week')}::DATE AS end_week,
                COALESCE({src('reason_code')}::VARCHAR, 'other') AS reason_code,
                COALESCE({src('status')}::VARCHAR, 'completed') AS status,
                COALESCE(
                    TRY_CAST({src('suppress_care_alerts')} AS BOOLEAN),
                    TRUE
                ) AS suppress_care_alerts,
                {src('note')}::VARCHAR AS note,
                {src('recorded_by')}::VARCHAR AS recorded_by,
                COALESCE({src('source')}::VARCHAR, 'import') AS source
            FROM {self.away_table}_raw
            WHERE {src('person')} IS NOT NULL
              AND {src('start_week')} IS NOT NULL
              AND {src('end_week')} IS NOT NULL
            """
        )
        self.con.execute(f"DROP TABLE {self.away_table}_raw")

    def _away_row_count(self) -> int:
        row = self.con.execute(
            f"SELECT COUNT(*) FROM {self.away_table}"
        ).fetchone()
        return int(row[0])

    def _query(self, sql: str, params: Optional[list] = None) -> pl.DataFrame:
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

    def away_intervals(self) -> pl.DataFrame:
        return self._query(
            f"""
            SELECT *
            FROM {self.away_table}
            ORDER BY person, start_week
            """
        )

    # ------------------------------------------------------------------
    # Core metrics (raw attendance — unchanged semantics)
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
    # Away-aware timeline
    # ------------------------------------------------------------------
    def _suppressing_away_sql(self) -> str:
        statuses = ", ".join(f"'{s}'" for s in AWAY_STATUSES)
        return f"""
            SELECT
                person,
                start_week,
                end_week,
                reason_code,
                status,
                suppress_care_alerts
            FROM {self.away_table}
            WHERE suppress_care_alerts = TRUE
              AND lower(status) IN ({statuses})
        """

    def person_timeline_summary(self, recent_weeks: int = 12) -> pl.DataFrame:
        """Per-person timeline with raw and unexplained-absence metrics."""
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
            ),
            suppressing_away AS (
                {self._suppressing_away_sql()}
            ),
            -- person-week explained flags on the global calendar
            person_cal AS (
                SELECT b.person, c.week
                FROM base b
                CROSS JOIN calendar c
            ),
            explained AS (
                SELECT DISTINCT pc.person, pc.week
                FROM person_cal pc
                JOIN suppressing_away aw
                  ON aw.person = pc.person
                 AND pc.week >= aw.start_week
                 AND pc.week <= aw.end_week
            ),
            -- unexplained weeks after last presence (care clock)
            unexplained_gap AS (
                SELECT
                    b.person,
                    COUNT(*) AS weeks_since_last_unexplained
                FROM base b
                JOIN calendar c
                  ON c.week > b.last_seen
                 AND c.week <= (SELECT max_week FROM bounds)
                LEFT JOIN explained e
                  ON e.person = b.person AND e.week = c.week
                WHERE e.week IS NULL
                GROUP BY b.person
            ),
            -- adjusted recent rate: exclude explained weeks from denominator
            recent_window_weeks AS (
                SELECT c.week
                FROM calendar c, bounds b
                WHERE c.week > b.max_week - INTERVAL '{recent_weeks} weeks'
                  AND c.week <= b.max_week
            ),
            recent_expected AS (
                SELECT
                    b.person,
                    COUNT(*) AS recent_expected_weeks
                FROM base b
                CROSS JOIN recent_window_weeks rw
                LEFT JOIN explained e
                  ON e.person = b.person AND e.week = rw.week
                WHERE e.week IS NULL
                  AND rw.week >= b.first_seen
                GROUP BY b.person
            ),
            recent_attended_expected AS (
                SELECT
                    b.person,
                    COUNT(*) AS recent_attended_expected
                FROM base b
                JOIN {self.table} a
                  ON a.person = b.person
                JOIN recent_window_weeks rw ON rw.week = a.week
                LEFT JOIN explained e
                  ON e.person = b.person AND e.week = a.week
                WHERE e.week IS NULL
                GROUP BY b.person
            ),
            explained_recent AS (
                SELECT
                    b.person,
                    COUNT(*) AS explained_weeks_recent
                FROM base b
                JOIN explained e ON e.person = b.person
                JOIN recent_window_weeks rw ON rw.week = e.week
                GROUP BY b.person
            ),
            known_away_now AS (
                SELECT DISTINCT aw.person
                FROM suppressing_away aw, bounds b
                WHERE b.max_week >= aw.start_week
                  AND b.max_week <= aw.end_week
            ),
            active_away_note AS (
                SELECT
                    aw.person,
                    string_agg(
                        aw.reason_code || ' ' || CAST(aw.start_week AS VARCHAR)
                        || '→' || CAST(aw.end_week AS VARCHAR),
                        '; '
                    ) AS active_away_detail
                FROM suppressing_away aw, bounds b
                WHERE b.max_week >= aw.start_week
                  AND b.max_week <= aw.end_week
                GROUP BY aw.person
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
                COALESCE(ug.weeks_since_last_unexplained, 0)
                    AS weeks_since_last_unexplained,
                date_diff('week', b.first_seen, bounds.max_week)
                    AS tenure_weeks,
                date_diff('week', b.first_seen, b.last_seen) + 1
                    AS span_weeks,
                b.weeks_attended * 1.0
                    / NULLIF(
                        date_diff('week', b.first_seen, bounds.max_week) + 1, 0
                    ) AS rate_since_first,
                COALESCE(ss.longest_streak, 1) AS longest_streak,
                COALESCE(ss.streak_at_last_seen, 1) AS streak_at_last_seen,
                CASE WHEN pl.person IS NOT NULL THEN TRUE ELSE FALSE END
                    AS present_latest_week,
                COALESCE(re.recent_expected_weeks, 0) AS recent_expected_weeks,
                COALESCE(rae.recent_attended_expected, 0)
                    AS recent_attended_expected,
                CASE
                    WHEN COALESCE(re.recent_expected_weeks, 0) > 0
                    THEN COALESCE(rae.recent_attended_expected, 0) * 1.0
                         / re.recent_expected_weeks
                    ELSE NULL
                END AS recent_rate_adjusted,
                CASE
                    WHEN COALESCE(re.recent_expected_weeks, 0) > 0
                    THEN COALESCE(rae.recent_attended_expected, 0) * 1.0
                         / re.recent_expected_weeks
                         - b.overall_rate
                    ELSE NULL
                END AS delta_adjusted,
                COALESCE(er.explained_weeks_recent, 0)
                    AS explained_weeks_recent,
                CASE WHEN kaw.person IS NOT NULL THEN TRUE ELSE FALSE END
                    AS known_away_now,
                aan.active_away_detail,
                bounds.max_week AS as_of_week
            FROM base b
            CROSS JOIN bounds
            LEFT JOIN recent r USING (person)
            LEFT JOIN streak_stats ss USING (person)
            LEFT JOIN present_latest pl USING (person)
            LEFT JOIN unexplained_gap ug USING (person)
            LEFT JOIN recent_expected re USING (person)
            LEFT JOIN recent_attended_expected rae USING (person)
            LEFT JOIN explained_recent er USING (person)
            LEFT JOIN known_away_now kaw USING (person)
            LEFT JOIN active_away_note aan USING (person)
            ORDER BY b.overall_rate DESC, b.person
            """
        )

    def _care_clock_col(self, respect_away: bool) -> str:
        if respect_away and self.has_away_data:
            return "weeks_since_last_unexplained"
        return "weeks_since_last"

    def _delta_col(self, respect_away: bool) -> str:
        if respect_away and self.has_away_data:
            return "delta_adjusted"
        return "delta"

    def _recent_rate_col(self, respect_away: bool) -> str:
        if respect_away and self.has_away_data:
            return "recent_rate_adjusted"
        return "recent_rate"

    # ------------------------------------------------------------------
    # Follow-up shortlists
    # ------------------------------------------------------------------
    def absence_watchlist(
        self,
        min_overall: float = 0.5,
        min_weeks_away: int = 2,
        recent_weeks: int = 12,
        respect_away: bool = True,
    ) -> pl.DataFrame:
        """Historically regular people with unexplained quiet period."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        clock = self._care_clock_col(respect_away)
        out = t.filter(
            (pl.col("overall_rate") >= min_overall)
            & (pl.col(clock) >= min_weeks_away)
            & (~pl.col("known_away_now") if respect_away else pl.lit(True))
        ).with_columns(
            pl.lit("Absence after reliability").alias("reason"),
            pl.lit("Gentle check-in").alias("suggested_action"),
            (
                pl.col(clock) * 2.0
                + pl.col("overall_rate") * 5.0
                + pl.col("longest_streak") * 0.3
            ).alias("priority_score"),
            pl.when(respect_away & self.has_away_data)
            .then(
                pl.format(
                    "unexplained_weeks={}",
                    pl.col("weeks_since_last_unexplained"),
                )
            )
            .otherwise(pl.lit("raw_calendar_gap"))
            .alias("suppression_note"),
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
        respect_away: bool = True,
    ) -> pl.DataFrame:
        """Sharp decline on expected weeks (explained leave excluded)."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        delta_c = self._delta_col(respect_away)
        clock = self._care_clock_col(respect_away)
        # Prefer adjusted delta when available; fall back to raw
        work = t.with_columns(
            pl.coalesce([pl.col(delta_c), pl.col("delta")]).alias("_delta_use")
        )
        filt = (
            (pl.col("_delta_use") <= max_delta)
            & (pl.col("tenure_weeks") >= min_history_weeks)
            & (pl.col("overall_rate") >= min_overall)
        )
        if respect_away and self.has_away_data:
            filt = filt & (~pl.col("known_away_now"))
            # need some expected weeks in window to judge decline
            filt = filt & (pl.col("recent_expected_weeks") >= 3)
        if exclude_fully_absent:
            filt = filt & (pl.col(clock) < min_weeks_away_for_absent)
        out = work.filter(filt).with_columns(
            pl.lit("Sharp recent decline").alias("reason"),
            pl.lit("Light-touch check-in").alias("suggested_action"),
            (
                pl.col("_delta_use").abs() * 8.0
                + pl.col("overall_rate") * 3.0
                + pl.col("tenure_weeks") * 0.05
            ).alias("priority_score"),
            pl.when(respect_away & self.has_away_data)
            .then(
                pl.format(
                    "delta_adj={}; explained_recent={}",
                    pl.col("_delta_use").round(3),
                    pl.col("explained_weeks_recent"),
                )
            )
            .otherwise(pl.lit("raw_delta"))
            .alias("suppression_note"),
        )
        return out.sort("priority_score", descending=True)

    def broken_streak_watchlist(
        self,
        min_streak: int = 4,
        recent_weeks: int = 12,
        min_weeks_away: int = 1,
        respect_away: bool = True,
    ) -> pl.DataFrame:
        """Broken streak only when the miss is unexplained."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        clock = self._care_clock_col(respect_away)
        out = t.filter(
            (pl.col("streak_at_last_seen") >= min_streak)
            & (pl.col(clock) >= min_weeks_away)
            & (~pl.col("known_away_now") if respect_away else pl.lit(True))
        ).with_columns(
            pl.lit("Broken attendance streak").alias("reason"),
            pl.lit("Timely, specific check-in").alias("suggested_action"),
            (
                pl.col("streak_at_last_seen") * 1.5
                + pl.col(clock) * 2.0
                + pl.col("overall_rate") * 3.0
            ).alias("priority_score"),
            pl.when(respect_away & self.has_away_data)
            .then(
                pl.format(
                    "unexplained_after_streak={}",
                    pl.col("weeks_since_last_unexplained"),
                )
            )
            .otherwise(pl.lit("raw_streak_break"))
            .alias("suppression_note"),
        )
        return out.sort("priority_score", descending=True)

    def returnee_watchlist(
        self,
        min_gap_weeks: int = 8,
        recent_window: int = 2,
        recent_weeks: int = 12,
        respect_away: bool = True,
    ) -> pl.DataFrame:
        """Return after long gap (optionally deprioritise fully explained gaps)."""
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
            ),
            suppressing_away AS (
                {self._suppressing_away_sql()}
            ),
            gap_weeks AS (
                SELECT
                    p.person,
                    c.week
                FROM prior p
                JOIN last_touch lt USING (person)
                JOIN calendar c
                  ON c.week > p.last_before_recent
                 AND c.week < lt.last_seen
            ),
            gap_explained AS (
                SELECT
                    g.person,
                    COUNT(*) AS gap_week_count,
                    COUNT(e.week) AS gap_explained_count
                FROM gap_weeks g
                LEFT JOIN (
                    SELECT DISTINCT pc.person, pc.week
                    FROM gap_weeks pc
                    JOIN suppressing_away aw
                      ON aw.person = pc.person
                     AND pc.week >= aw.start_week
                     AND pc.week <= aw.end_week
                ) e ON e.person = g.person AND e.week = g.week
                GROUP BY g.person
            )
            SELECT
                lt.person,
                lt.last_seen,
                p.last_before_recent,
                date_diff('week', p.last_before_recent, lt.last_seen)
                    AS gap_weeks,
                COALESCE(rh.hits_recent, 0) AS hits_recent,
                COALESCE(ge.gap_week_count, 0) AS gap_week_count,
                COALESCE(ge.gap_explained_count, 0) AS gap_explained_count,
                CASE
                    WHEN COALESCE(ge.gap_week_count, 0) > 0
                     AND COALESCE(ge.gap_explained_count, 0)
                         = COALESCE(ge.gap_week_count, 0)
                    THEN TRUE
                    ELSE FALSE
                END AS gap_fully_explained,
                b.max_week AS as_of_week
            FROM last_touch lt
            CROSS JOIN bounds b
            JOIN prior p USING (person)
            LEFT JOIN recent_hits rh USING (person)
            LEFT JOIN gap_explained ge USING (person)
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
                pl.lit(None, dtype=pl.Utf8).alias("suppression_note"),
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
        )
        if respect_away and self.has_away_data:
            # Deprioritise fully explained gaps (still visible but low score)
            out = out.with_columns(
                pl.when(pl.col("gap_fully_explained"))
                .then(pl.lit("Back from planned away"))
                .otherwise(pl.lit("Return after long gap"))
                .alias("reason"),
                pl.when(pl.col("gap_fully_explained"))
                .then(pl.lit("Welcome back from leave"))
                .otherwise(pl.lit("Warm re-welcome"))
                .alias("suggested_action"),
                (
                    pl.col("gap_weeks") * 0.5
                    + pl.col("hits_recent") * 2.0
                    + pl.col("overall_rate").fill_null(0) * 2.0
                    - pl.when(pl.col("gap_fully_explained"))
                    .then(pl.lit(20.0))
                    .otherwise(pl.lit(0.0))
                ).alias("priority_score"),
                pl.when(pl.col("gap_fully_explained"))
                .then(pl.lit("gap_fully_explained"))
                .otherwise(pl.lit("unexplained_or_mixed_gap"))
                .alias("suppression_note"),
            )
        else:
            out = out.with_columns(
                pl.lit("Return after long gap").alias("reason"),
                pl.lit("Warm re-welcome").alias("suggested_action"),
                (
                    pl.col("gap_weeks") * 0.5
                    + pl.col("hits_recent") * 2.0
                    + pl.col("overall_rate").fill_null(0) * 2.0
                ).alias("priority_score"),
                pl.lit("away_not_applied").alias("suppression_note"),
            )
        return out.sort("priority_score", descending=True)

    # ------------------------------------------------------------------
    # New / connect-in
    # ------------------------------------------------------------------
    def newcomers(
        self, within_weeks: int = 12, recent_weeks: int = 12
    ) -> pl.DataFrame:
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
                pl.lit("").alias("suppression_note"),
            )
        )
        return out.sort("priority_score", descending=True)

    def new_and_fading(
        self,
        within_weeks: int = 12,
        max_attendances: int = 3,
        min_weeks_away: int = 2,
        recent_weeks: int = 12,
        respect_away: bool = True,
    ) -> pl.DataFrame:
        """New people gone quiet on an unexplained basis."""
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        clock = self._care_clock_col(respect_away)
        out = t.filter(
            (pl.col("tenure_weeks") <= within_weeks)
            & (pl.col("weeks_attended") <= max_attendances)
            & (pl.col(clock) >= min_weeks_away)
            & (~pl.col("known_away_now") if respect_away else pl.lit(True))
        ).with_columns(
            pl.lit("New but fading").alias("reason"),
            pl.lit("Early hospitality follow-up").alias("suggested_action"),
            (
                pl.col(clock) * 2.0
                + (max_attendances - pl.col("weeks_attended")) * 1.5
                + pl.col("rate_since_first").fill_null(0) * 2.0
            ).alias("priority_score"),
            pl.when(respect_away & self.has_away_data)
            .then(
                pl.format(
                    "unexplained_weeks={}",
                    pl.col("weeks_since_last_unexplained"),
                )
            )
            .otherwise(pl.lit("raw_gap"))
            .alias("suppression_note"),
        )
        return out.sort("priority_score", descending=True)

    def emerging_regulars(
        self,
        min_tenure_weeks: int = 8,
        max_tenure_weeks: int = 26,
        min_rate_since_first: float = 0.5,
        min_recent_rate: float = 0.5,
        recent_weeks: int = 12,
        respect_away: bool = True,
    ) -> pl.DataFrame:
        t = self.person_timeline_summary(recent_weeks=recent_weeks)
        recent_c = self._recent_rate_col(respect_away)
        work = t.with_columns(
            pl.coalesce([pl.col(recent_c), pl.col("recent_rate")]).alias(
                "_recent_use"
            )
        )
        out = work.filter(
            (pl.col("tenure_weeks") >= min_tenure_weeks)
            & (pl.col("tenure_weeks") <= max_tenure_weeks)
            & (pl.col("rate_since_first") >= min_rate_since_first)
            & (pl.col("_recent_use") >= min_recent_rate)
        ).with_columns(
            pl.lit("Emerging regular").alias("reason"),
            pl.lit("Thank and invite deeper").alias("suggested_action"),
            (
                pl.col("_recent_use") * 5.0
                + pl.col("rate_since_first") * 3.0
                + pl.col("longest_streak") * 0.2
            ).alias("priority_score"),
            pl.lit("").alias("suppression_note"),
        )
        return out.sort("priority_score", descending=True)

    def second_visit_funnel(self, return_within_weeks: int = 4) -> pl.DataFrame:
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
        respect_away: bool = True,
    ) -> dict[str, pl.DataFrame]:
        """Bundle shortlists; respect_away uses unexplained care clocks."""
        absence = self.absence_watchlist(
            min_overall=max(0.45, core_threshold - 0.1),
            min_weeks_away=min_weeks_away,
            recent_weeks=recent_weeks,
            respect_away=respect_away,
        )
        decline = self.decline_watchlist(
            recent_weeks=recent_weeks,
            max_delta=-0.2,
            min_history_weeks=8,
            min_overall=0.25,
            min_weeks_away_for_absent=min_weeks_away,
            respect_away=respect_away,
        )
        broken = self.broken_streak_watchlist(
            min_streak=4,
            recent_weeks=recent_weeks,
            min_weeks_away=1,
            respect_away=respect_away,
        )
        returnees = self.returnee_watchlist(
            min_gap_weeks=8,
            recent_window=2,
            recent_weeks=recent_weeks,
            respect_away=respect_away,
        )
        sticky = self.new_and_persistent(
            within_weeks=new_within_weeks,
            recent_weeks=recent_weeks,
        )
        fading = self.new_and_fading(
            within_weeks=new_within_weeks,
            recent_weeks=recent_weeks,
            min_weeks_away=min_weeks_away,
            respect_away=respect_away,
        )
        emerging = self.emerging_regulars(
            recent_weeks=recent_weeks,
            min_rate_since_first=max(0.45, core_threshold - 0.1),
            respect_away=respect_away,
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
            "timeline": self.person_timeline_summary(
                recent_weeks=recent_weeks
            ),
            "away_intervals": self.away_intervals(),
        }

    def add_service_filter(self, service_type: Optional[str] = None) -> None:
        """Placeholder for when the source table has service_type etc."""
        pass
