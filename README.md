# Attendance Analyser

Reactive [Marimo](https://marimo.io) notebook for weekly event attendance analysis.

Analysis logic lives in a pure Python class (`AttendanceAnalyser`) backed by an
in-memory DuckDB table. Marimo cells only bind UI controls and render Plotly
charts.

## Data format

Long-format CSV with one row per person per week attended:

| week       | person |
|------------|--------|
| 2024-01-07 | P01    |
| 2024-01-07 | P02    |

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
10. Frequent-attendee heatmap
11. Recent vs overall scatter
12. Separation-of-concerns note

## Public API

| Method | Returns |
|--------|---------|
| `n_weeks()` | `int` |
| `attendance_rates()` | Polars: `person`, `weeks_attended`, `attendance_rate` |
| `core_group(threshold)` | Polars subset of rates |
| `weekly_totals(threshold)` | Polars: `week`, `total_attendees`, `core_present` |
| `heatmap_data(min_rate)` | Polars: `person`, `week`, `attended` |
| `recency_comparison(recent_weeks, min_overall=0.2)` | Polars: `person`, `overall_rate`, `recent_rate`, `delta` |
