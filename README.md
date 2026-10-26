# Attendance Analyser

[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/DataBooth/attendance-analyser/blob/main/attendance_analyser_notebook.py)

Reactive [Marimo](https://marimo.io) notebook for weekly event attendance analysis.

Analysis logic lives in a pure Python class (`AttendanceAnalyser`) backed by an
in-memory DuckDB table. Marimo cells only bind UI controls and render Plotly
charts.

## Try it (molab)

| Mode | Link |
|------|------|
| Static preview | [molab GitHub preview](https://molab.marimo.io/github/DataBooth/attendance-analyser/blob/main/attendance_analyser_notebook.py) |
| Interactive (WASM) | [molab WASM](https://molab.marimo.io/github/DataBooth/attendance-analyser/blob/main/attendance_analyser_notebook.py/wasm) |

For full server Python (recommended for DuckDB + CSV), open
[molab.marimo.io](https://molab.marimo.io), create a notebook from the GitHub URL
above, then use **Share**. GitHub remains the source of truth for synced notebooks.

Generate badges/links at [molab.marimo.io/github](https://molab.marimo.io/github).

Static previews include rendered outputs when
`__marimo__/session/attendance_analyser_notebook.py.json` is committed
(regenerate with `just session`).

## Data format

Long-format CSV with one row per person per week attended:

| week       | person |
|------------|--------|
| 2025-01-05 | P001   |
| 2025-01-05 | P002   |

## Quick start

```bash
just init
just synth   # optional — regenerates artifacts/synthetic_attendance.csv
just test
just edit    # marimo edit attendance_analyser_notebook.py
```

Or without `just`:

```bash
uv sync
uv run python scripts/generate_synthetic_attendance.py
uv run python scripts/smoke_test.py
uv run marimo edit attendance_analyser_notebook.py
```

## Notebook layout

1. Imports
2. `AttendanceAnalyser` class (DuckDB + Polars, no UI)
3. Markdown header
4. Instantiation (local `artifacts/` path, with `/workspace/...` fallback)
5. Core threshold and recent-window sliders
6. Summary metrics
7. Attendance-rate histogram
8. Core group table
9. Weekly total vs core line chart
10. Week-on-week overlap (retention, Jaccard, shared/newcomers/leavers)
11. Frequent-attendee heatmap
12. Recent vs overall scatter
13. Separation-of-concerns note

## Public API

| Method | Returns |
|--------|---------|
| `n_weeks()` | `int` |
| `attendance_rates()` | Polars: `person`, `weeks_attended`, `attendance_rate` |
| `core_group(threshold)` | Polars subset of rates |
| `weekly_totals(threshold)` | Polars: `week`, `total_attendees`, `core_present` |
| `heatmap_data(min_rate)` | Polars: `person`, `week`, `attended` |
| `recency_comparison(recent_weeks, min_overall=0.2)` | Polars: `person`, `overall_rate`, `recent_rate`, `delta` |
| `week_on_week_overlap()` | Polars: `prev_week`, `week`, `prev_count`, `curr_count`, `shared`, `newcomers`, `leavers`, `retention`, `jaccard` |
