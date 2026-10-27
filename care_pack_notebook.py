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

    _root = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    from attendance_logic import AttendanceAnalyser

    return AttendanceAnalyser, Path, go, mo, pl, px


@app.cell
def _(mo):
    mo.md(r"""
# This week's care pack

Shortlists for **gentle check-ins** and **connecting people in**.
These are prompts for human care — absence is not automatically a problem.

Logic: `AttendanceAnalyser` in `attendance_logic/`. Overview charts:
`overview_notebook.py`.

Optional **away intervals** CSV pauses care clocks for holidays/sickness
(see `docs/proposal-excused-absences.md`).
""")
    return


@app.cell
def _(AttendanceAnalyser, Path):
    _att_candidates = [
        Path("artifacts/synthetic_attendance.csv"),
        Path("/workspace/artifacts/synthetic_attendance.csv"),
    ]
    _away_candidates = [
        Path("artifacts/synthetic_away_intervals.csv"),
        Path("/workspace/artifacts/synthetic_away_intervals.csv"),
    ]
    _csv_path = next((p for p in _att_candidates if p.exists()), _att_candidates[0])
    _away_path = next((p for p in _away_candidates if p.exists()), None)
    analyser = AttendanceAnalyser(_csv_path, away_csv=_away_path)
    return (analyser,)


@app.cell
def _(mo):
    threshold = mo.ui.slider(
        0.3, 0.9, value=0.6, step=0.05, label="Core threshold", show_value=True
    )
    recent_weeks = mo.ui.slider(
        4, 26, value=12, step=1, label="Recent window (weeks)", show_value=True
    )
    min_weeks_away = mo.ui.slider(
        1, 6, value=2, step=1, label="Min weeks away (check-in)", show_value=True
    )
    new_within = mo.ui.slider(
        4, 26, value=12, step=1, label="New window (weeks)", show_value=True
    )
    top_n = mo.ui.slider(
        5, 30, value=15, step=1, label="Top N per list", show_value=True
    )
    respect_away = mo.ui.switch(
        value=True,
        label="Respect known away (excused absences)",
    )
    mo.vstack(
        [
            mo.hstack([threshold, recent_weeks, min_weeks_away], justify="start"),
            mo.hstack([new_within, top_n, respect_away], justify="start"),
        ]
    )
    return min_weeks_away, new_within, recent_weeks, respect_away, threshold, top_n


@app.cell
def _(
    analyser,
    min_weeks_away,
    mo,
    new_within,
    recent_weeks,
    respect_away,
    threshold,
    top_n,
):
    pack = analyser.care_pack(
        core_threshold=threshold.value,
        recent_weeks=recent_weeks.value,
        min_weeks_away=min_weeks_away.value,
        new_within_weeks=new_within.value,
        top_n=top_n.value,
        respect_away=respect_away.value,
    )
    _away_n = pack["away_intervals"].height if "away_intervals" in pack else 0
    _mode = "respecting known away" if respect_away.value else "raw calendar gaps"
    mo.md(
        f"""
**As of** {analyser.max_week()}  |  **Weeks in data:** {analyser.n_weeks()}  |  **Mode:** {_mode}

Away intervals loaded: **{_away_n}** (see table below). Excused weeks pause check-in clocks.

| List | Count (top N) |
|------|----------------|
| Absence after reliability | {pack['absence'].height} |
| Sharp decline | {pack['decline'].height} |
| Broken streak | {pack['broken_streak'].height} |
| Returnees | {pack['returnees'].height} |
| New & persistent | {pack['new_persistent'].height} |
| New & fading | {pack['new_fading'].height} |
| Emerging regulars | {pack['emerging_regulars'].height} |
"""
    )
    return (pack,)


@app.cell
def _(mo, pack):
    _away = pack.get("away_intervals")
    if _away is None or _away.height == 0:
        _away_view = mo.md("_No away intervals loaded — using attendance only._")
    else:
        _away_view = mo.ui.table(_away, label="Known away / excused intervals")
    _away_view
    return


@app.cell
def _(mo):
    mo.md(r"""
## Follow up — worth a check-in
""")
    return


@app.cell
def _(mo, pack):
    _cols = [
        c
        for c in [
            "person",
            "reason",
            "suggested_action",
            "weeks_since_last",
            "weeks_since_last_unexplained",
            "known_away_now",
            "overall_rate",
            "recent_rate",
            "delta",
            "longest_streak",
            "streak_at_last_seen",
            "priority_score",
            "last_seen",
            "suppression_note",
            "active_away_detail",
        ]
        if c in pack["absence"].columns
    ]
    mo.ui.table(
        pack["absence"].select(_cols) if pack["absence"].height else pack["absence"],
        label="Absence after reliability",
    )
    return


@app.cell
def _(mo, pack):
    _cols = [
        c
        for c in [
            "person",
            "reason",
            "suggested_action",
            "overall_rate",
            "recent_rate",
            "delta",
            "weeks_since_last",
            "priority_score",
        ]
        if c in pack["decline"].columns
    ]
    mo.ui.table(
        pack["decline"].select(_cols) if pack["decline"].height else pack["decline"],
        label="Sharp recent decline",
    )
    return


@app.cell
def _(mo, pack):
    _cols = [
        c
        for c in [
            "person",
            "reason",
            "suggested_action",
            "streak_at_last_seen",
            "weeks_since_last",
            "overall_rate",
            "priority_score",
        ]
        if c in pack["broken_streak"].columns
    ]
    mo.ui.table(
        pack["broken_streak"].select(_cols)
        if pack["broken_streak"].height
        else pack["broken_streak"],
        label="Broken attendance streak",
    )
    return


@app.cell
def _(mo, pack):
    _cols = [
        c
        for c in [
            "person",
            "reason",
            "suggested_action",
            "gap_weeks",
            "hits_recent",
            "last_before_recent",
            "last_seen",
            "overall_rate",
            "priority_score",
        ]
        if c in pack["returnees"].columns
    ]
    mo.ui.table(
        pack["returnees"].select(_cols)
        if pack["returnees"].height
        else pack["returnees"],
        label="Returnees (re-welcome)",
    )
    return


@app.cell
def _(pack, pl, px):
    _parts = []
    for _name, _key in [
        ("Absence", "absence"),
        ("Decline", "decline"),
        ("Broken streak", "broken_streak"),
        ("Returnee", "returnees"),
    ]:
        _df = pack[_key]
        if _df.height and "priority_score" in _df.columns:
            _parts.append(
                _df.select(["person", "priority_score"]).with_columns(
                    pl.lit(_name).alias("list")
                )
            )
    if not _parts:
        fig_follow = px.bar(title="No follow-up rows for current thresholds")
    else:
        follow = pl.concat(_parts).sort("priority_score", descending=True).head(25)
        fig_follow = px.bar(
            follow.to_pandas(),
            x="priority_score",
            y="person",
            color="list",
            orientation="h",
            title="Follow-up priority (top combined)",
            labels={"priority_score": "Priority score", "person": "Person"},
        )
        fig_follow.update_layout(
            height=max(400, follow.height * 22),
            yaxis=dict(autorange="reversed"),
        )
    fig_follow
    return (fig_follow,)


@app.cell
def _(mo):
    mo.md(r"""
## Connect in — new and becoming persistent
""")
    return


@app.cell
def _(mo, pack):
    _cols = [
        c
        for c in [
            "person",
            "reason",
            "suggested_action",
            "first_seen",
            "weeks_attended",
            "rate_since_first",
            "hits_last_window",
            "recent_rate",
            "priority_score",
        ]
        if c in pack["new_persistent"].columns
    ]
    mo.ui.table(
        pack["new_persistent"].select(_cols)
        if pack["new_persistent"].height
        else pack["new_persistent"],
        label="New and persistent — connect into community",
    )
    return


@app.cell
def _(mo, pack):
    _cols = [
        c
        for c in [
            "person",
            "reason",
            "suggested_action",
            "first_seen",
            "last_seen",
            "weeks_attended",
            "weeks_since_last",
            "rate_since_first",
            "priority_score",
        ]
        if c in pack["new_fading"].columns
    ]
    mo.ui.table(
        pack["new_fading"].select(_cols)
        if pack["new_fading"].height
        else pack["new_fading"],
        label="New but fading — early hospitality follow-up",
    )
    return


@app.cell
def _(mo, pack):
    _cols = [
        c
        for c in [
            "person",
            "reason",
            "suggested_action",
            "first_seen",
            "tenure_weeks",
            "rate_since_first",
            "recent_rate",
            "longest_streak",
            "priority_score",
        ]
        if c in pack["emerging_regulars"].columns
    ]
    mo.ui.table(
        pack["emerging_regulars"].select(_cols)
        if pack["emerging_regulars"].height
        else pack["emerging_regulars"],
        label="Emerging regulars — thank and invite deeper",
    )
    return


@app.cell
def _(pack, pl, px):
    _parts = []
    for _name, _key in [
        ("New sticky", "new_persistent"),
        ("New fading", "new_fading"),
        ("Emerging", "emerging_regulars"),
    ]:
        _df = pack[_key]
        if _df.height and "priority_score" in _df.columns:
            _parts.append(
                _df.select(["person", "priority_score"]).with_columns(
                    pl.lit(_name).alias("list")
                )
            )
    if not _parts:
        fig_connect = px.bar(title="No connect-in rows for current thresholds")
    else:
        conn = pl.concat(_parts).sort("priority_score", descending=True).head(25)
        fig_connect = px.bar(
            conn.to_pandas(),
            x="priority_score",
            y="person",
            color="list",
            orientation="h",
            title="Connect-in priority (top combined)",
        )
        fig_connect.update_layout(
            height=max(400, conn.height * 22),
            yaxis=dict(autorange="reversed"),
        )
    fig_connect
    return (fig_connect,)


@app.cell
def _(mo):
    mo.md(r"""
## Second-visit funnel (hospitality health)
""")
    return


@app.cell
def _(pack, px):
    _funnel = pack["funnel"]
    if _funnel.height == 0:
        fig_funnel = px.line(title="No funnel cohorts yet")
    else:
        _fdf = _funnel.to_pandas()
        fig_funnel = px.line(
            _fdf,
            x="cohort_week",
            y=["return_rate", "sticky_rate"],
            title="Cohort return (≤4 weeks) and sticky-at-8-weeks rates",
            labels={"value": "Rate", "variable": "Metric"},
            markers=True,
        )
        fig_funnel.update_layout(
            height=400, yaxis_tickformat=".0%", legend_title_text=""
        )
    fig_funnel
    return (fig_funnel,)


@app.cell
def _(pack, px):
    _funnel_c = pack["funnel"]
    if _funnel_c.height == 0:
        fig_funnel_counts = px.bar(title="No funnel counts")
    else:
        _fdf_c = _funnel_c.tail(16).to_pandas()
        fig_funnel_counts = px.bar(
            _fdf_c,
            x="cohort_week",
            y=["first_visits", "returned_within_window", "sticky_at_8w"],
            barmode="group",
            title="Recent cohorts: first visits → returned → sticky@8w",
            labels={"value": "People", "variable": "Stage"},
        )
        fig_funnel_counts.update_layout(height=400, legend_title_text="")
    fig_funnel_counts
    return (fig_funnel_counts,)


@app.cell
def _(pack, px):
    _timeline = pack["timeline"]
    fig_life = px.scatter(
        _timeline.to_pandas(),
        x="tenure_weeks",
        y="rate_since_first",
        color="weeks_since_last",
        hover_name="person",
        title="Life-cycle map: tenure vs rate since first (colour = weeks since last)",
        labels={
            "tenure_weeks": "Weeks since first seen",
            "rate_since_first": "Attendance rate since first seen",
            "weeks_since_last": "Weeks since last",
        },
        color_continuous_scale="YlOrRd",
    )
    fig_life.update_layout(height=480)
    fig_life
    return (fig_life,)


@app.cell
def _(mo):
    mo.md(r"""
### How to use

1. Scan **Absence** and **Decline** first for pastoral check-ins.
2. Use **New & persistent** for welcome / small-group / team intros.
3. Use **New & fading** for early hospitality follow-up (different script).
4. Watch the **funnel** for process issues (not only individuals).
5. Adjust sliders if lists are too long or too sparse.

See `roadmap.md` for definitions, ethics, and next phases.
""")
    return


if __name__ == "__main__":
    app.run()
