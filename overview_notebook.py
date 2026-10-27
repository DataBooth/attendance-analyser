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
    import polars as pl
    import plotly.express as px
    import plotly.graph_objects as go
    from pathlib import Path
    import sys

    # Allow `marimo edit` from repo root without install
    _root = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    from attendance_logic import AttendanceAnalyser

    return AttendanceAnalyser, Path, go, mo, pl, px


@app.cell
def _(mo):
    mo.md(r"""
# Weekly Event Attendance Analysis

Overview metrics for the gathering. Pastoral **check-in** and **connect-in**
shortlists live in the companion notebook
`care_pack_notebook.py` (same `AttendanceAnalyser` library).
""")
    return


@app.cell
def _(AttendanceAnalyser, Path):
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
        0.3, 0.9, value=0.6, step=0.05, label="Core threshold", show_value=True
    )
    recent_weeks = mo.ui.slider(
        4, 26, value=12, step=1, label="Recent window (weeks)", show_value=True
    )
    mo.hstack([threshold, recent_weeks], justify="start")
    return recent_weeks, threshold


@app.cell
def _(analyser, mo, threshold):
    n_weeks = analyser.n_weeks()
    core = analyser.core_group(threshold.value)
    mo.md(
        f"**Total weeks:** {n_weeks}  |  "
        f"**Core (≥{threshold.value:.0%})**: {core.height} people  |  "
        f"**As of:** {analyser.max_week()}"
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
        )
    )
    fig_overlap.add_trace(
        go.Scatter(
            x=odf["week"],
            y=odf["jaccard"],
            mode="lines+markers",
            name="Jaccard (shared ÷ union)",
        )
    )
    fig_overlap.add_trace(
        go.Bar(
            x=odf["week"],
            y=odf["shared"],
            name="Shared people",
            opacity=0.35,
            yaxis="y2",
        )
    )
    fig_overlap.update_layout(
        title="Week-on-week attendee overlap",
        height=450,
        yaxis=dict(title="Overlap rate", tickformat=".0%", range=[0, 1]),
        yaxis2=dict(
            title="Shared people", overlaying="y", side="right", showgrid=False
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
        fig_heat.update_layout(height=max(400, min(900, len(pivot) * 12)))
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
        labels={"overall_rate": "Overall rate", "recent_rate": "Recent rate"},
    )
    fig_recency.add_shape(
        type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dash", color="gray")
    )
    fig_recency.update_layout(height=450)
    fig_recency
    return (fig_recency,)


@app.cell
def _(mo):
    mo.md(r"""
### Next step

Open **`care_pack_notebook.py`** for ranked follow-up and connect-in lists
(absence, decline, broken streaks, returnees, new & persistent, new & fading,
emerging regulars, and the second-visit funnel).
""")
    return


if __name__ == "__main__":
    app.run()
