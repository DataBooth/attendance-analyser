# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "marimo",
#   "duckdb",
#   "polars",
#   "plotly",
#   "pandas",
#   "pyarrow",
# ]
# ///

import marimo

__generated_with = "0.9.14"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import duckdb
    import polars as pl
    import plotly.express as px
    import plotly.graph_objects as go
    import pandas as pd
    from pathlib import Path
    from typing import Optional

    return mo, duckdb, pl, px, go, pd, Path, Optional


# ---------------------------------------------------------------------------
# Analysis class — pure logic, no UI
# ---------------------------------------------------------------------------
@app.cell
def _(duckdb, pl, Path, Optional):
    class AttendanceAnalyser:
        """Encapsulates all attendance analysis logic against a DuckDB table.

        Note: in-memory anonymisation (stable token mapping of person IDs) can
        be added later without changing the public methods.
        """

        def __init__(self, csv_path: str | Path, table: str = "attendance"):
            self.con = duckdb.connect(":memory:")
            self.table = table
            self._load(csv_path)

        def _load(self, csv_path: str | Path) -> None:
            path = Path(csv_path).expanduser().resolve()
            if not path.exists():
                raise FileNotFoundError(f"Attendance CSV not found: {path}")
            # DuckDB paths use forward slashes on all platforms
            path_str = path.as_posix()
            self.con.execute(
                f"""
                CREATE TABLE {self.table} AS
                SELECT
                    week::DATE AS week,
                    person,
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
            """Consecutive-week attendee overlap metrics.

            For each week after the first, returns:
            - shared: people present in both this week and the previous week
            - retention: shared / previous week headcount
            - jaccard: shared / union of the two weeks
            - newcomers / leavers relative to the previous week
            """
            return self._query(
                f"""
                WITH weeks AS (
                    SELECT DISTINCT week
                    FROM {self.table}
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
                    JOIN {self.table} curr
                      ON curr.week = p.week
                    JOIN {self.table} prev
                      ON prev.week = p.prev_week
                     AND prev.person = curr.person
                    GROUP BY p.week, p.prev_week
                ),
                counts AS (
                    SELECT week, COUNT(*) AS n
                    FROM {self.table}
                    GROUP BY week
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

        def add_service_filter(self, service_type: Optional[str] = None) -> None:
            """Placeholder for when the source table has service_type etc."""
            pass

    return (AttendanceAnalyser,)


# ---------------------------------------------------------------------------
# UI / presentation layer
# ---------------------------------------------------------------------------
@app.cell
def _(mo):
    mo.md(r"""
# Weekly Event Attendance Analysis

Logic lives in `AttendanceAnalyser`. Cells below only wire UI controls
and render results — no analysis SQL in the presentation layer.
""")
    return


@app.cell
def _(AttendanceAnalyser, Path):
    # Prefer local synthetic data; fall back to the workspace path used in CI/docs
    _candidates = [
        Path("artifacts/synthetic_attendance.csv"),
        Path("/workspace/artifacts/synthetic_attendance.csv"),
    ]
    _csv_path = next((p for p in _candidates if p.exists()), _candidates[0])
    analyser = AttendanceAnalyser(_csv_path)
    return (analyser,)


@app.cell
def _(mo):
    threshold = mo.ui.slider(
        0.3,
        0.9,
        value=0.6,
        step=0.05,
        label="Core threshold",
        show_value=True,
    )
    recent_weeks = mo.ui.slider(
        4,
        26,
        value=12,
        step=1,
        label="Recent window (weeks)",
        show_value=True,
    )
    mo.hstack([threshold, recent_weeks], justify="start")
    return threshold, recent_weeks


@app.cell
def _(analyser, mo, threshold):
    n_weeks = analyser.n_weeks()
    core = analyser.core_group(threshold.value)
    mo.md(
        f"**Total weeks:** {n_weeks}  |  "
        f"**Core (≥{threshold.value:.0%})**: {core.height} people"
    )
    return core, n_weeks


@app.cell
def _(analyser, px, threshold):
    rates = analyser.attendance_rates()
    fig_dist = px.histogram(
        rates.to_pandas(),
        x="attendance_rate",
        nbins=25,
        title="Distribution of attendance rates",
        labels={"attendance_rate": "Proportion of weeks attended"},
    )
    fig_dist.add_vline(
        x=threshold.value,
        line_dash="dash",
        line_color="red",
        annotation_text="Core threshold",
    )
    fig_dist.update_layout(height=400)
    fig_dist
    return (fig_dist,)


@app.cell
def _(core, mo):
    mo.ui.table(core, label="Core group")
    return


@app.cell
def _(analyser, px, threshold):
    weekly = analyser.weekly_totals(threshold.value)
    fig_weekly = px.line(
        weekly.to_pandas(),
        x="week",
        y=["total_attendees", "core_present"],
        title="Weekly attendance: total vs core",
        labels={"value": "People", "variable": "Series"},
        markers=True,
    )
    fig_weekly.update_layout(height=400, legend_title_text="")
    fig_weekly
    return (fig_weekly,)


@app.cell
def _(analyser, mo):
    overlap = analyser.week_on_week_overlap()
    mo.md(
        f"**Week-on-week overlap** — "
        f"mean retention {overlap['retention'].mean():.0%}, "
        f"mean Jaccard {overlap['jaccard'].mean():.0%}, "
        f"mean shared {overlap['shared'].mean():.0f} people "
        f"(newcomers {overlap['newcomers'].mean():.0f} / "
        f"leavers {overlap['leavers'].mean():.0f})"
    )
    return (overlap,)


@app.cell
def _(go, overlap):
    odf = overlap.to_pandas()
    fig_overlap = go.Figure()
    fig_overlap.add_trace(
        go.Scatter(
            x=odf["week"],
            y=odf["retention"],
            mode="lines+markers",
            name="Retention (shared ÷ previous week)",
            hovertemplate=(
                "%{x|%Y-%m-%d}<br>Retention: %{y:.1%}"
                "<br>Shared: %{customdata[0]}"
                "<br>Prev: %{customdata[1]} → Curr: %{customdata[2]}"
                "<extra></extra>"
            ),
            customdata=odf[["shared", "prev_count", "curr_count"]].to_numpy(),
        )
    )
    fig_overlap.add_trace(
        go.Scatter(
            x=odf["week"],
            y=odf["jaccard"],
            mode="lines+markers",
            name="Jaccard (shared ÷ union)",
            hovertemplate="%{x|%Y-%m-%d}<br>Jaccard: %{y:.1%}<extra></extra>",
        )
    )
    fig_overlap.add_trace(
        go.Bar(
            x=odf["week"],
            y=odf["shared"],
            name="Shared people",
            opacity=0.35,
            yaxis="y2",
            hovertemplate="%{x|%Y-%m-%d}<br>Shared: %{y}<extra></extra>",
        )
    )
    fig_overlap.update_layout(
        title="Week-on-week attendee overlap",
        height=450,
        yaxis=dict(title="Overlap rate", tickformat=".0%", range=[0, 1]),
        yaxis2=dict(
            title="Shared people",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        barmode="overlay",
    )
    fig_overlap
    return (fig_overlap,)


@app.cell
def _(overlap, px):
    flow = overlap.select(["week", "newcomers", "leavers", "shared"]).to_pandas()
    fig_flow = px.bar(
        flow,
        x="week",
        y=["shared", "newcomers", "leavers"],
        title="Week-on-week composition: shared, newcomers, leavers",
        labels={"value": "People", "variable": "Group"},
        barmode="group",
    )
    fig_flow.update_layout(height=400, legend_title_text="")
    fig_flow
    return (fig_flow,)


@app.cell
def _(analyser, px, threshold):
    heat = analyser.heatmap_data(min_rate=max(0.25, threshold.value - 0.25))
    if heat.height == 0:
        fig_heat = px.imshow([[0]], title="No data for heatmap")
    else:
        pivot = (
            heat.to_pandas()
            .pivot(index="person", columns="week", values="attended")
            .fillna(0)
        )
        pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
        fig_heat = px.imshow(
            pivot,
            title="Attendance heatmap (frequent attendees)",
            color_continuous_scale="Blues",
            aspect="auto",
            labels=dict(x="Week", y="Person", color="Attended"),
        )
        fig_heat.update_layout(height=max(400, len(pivot) * 12))
    fig_heat
    return (fig_heat,)


@app.cell
def _(analyser, px, recent_weeks):
    recency = analyser.recency_comparison(recent_weeks.value)
    fig_recency = px.scatter(
        recency.to_pandas(),
        x="overall_rate",
        y="recent_rate",
        hover_name="person",
        title="Recent vs overall attendance rate (above diagonal = rising)",
        labels={
            "overall_rate": "Overall rate",
            "recent_rate": "Recent rate",
        },
    )
    fig_recency.add_shape(
        type="line",
        x0=0,
        y0=0,
        x1=1,
        y1=1,
        line=dict(dash="dash", color="gray"),
    )
    fig_recency.update_layout(height=450)
    fig_recency
    return (fig_recency,)


@app.cell
def _(mo):
    mo.md(r"""
### Separation notes

- All SQL and metric logic is inside `AttendanceAnalyser`.
- Marimo cells only instantiate the class, bind UI controls, and call methods.
- The class can be moved to its own module (`attendance.py`) and imported
  if you want even cleaner separation.
""")
    return


if __name__ == "__main__":
    app.run()
