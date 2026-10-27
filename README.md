# Attendance Analyser

[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/DataBooth/attendance-analyser/blob/main/overview_notebook.py)

Reactive [Marimo](https://marimo.io) notebooks for weekly event attendance analysis
and pastoral **care packs** (check-in and connect-in shortlists).

Analysis logic lives in the pure Python package `attendance_logic`
(`AttendanceAnalyser` + DuckDB). Marimo cells only bind UI controls and render
Plotly charts / tables.

## Notebooks

| Notebook | Purpose |
|----------|---------|
| `overview_notebook.py` | Overview: rates, core, weekly totals, overlap, heatmap, recency |
| `care_pack_notebook.py` | **This week’s care pack**: absence, decline, streaks, returnees, new sticky / fading, emerging regulars, second-visit funnel |

```bash
just edit        # overview
just edit-care   # pastoral shortlists
```

## Try it (molab)

| Mode | Link |
|------|------|
| Overview (static) | [molab preview](https://molab.marimo.io/github/DataBooth/attendance-analyser/blob/main/overview_notebook.py) |
| Overview (WASM) | [molab WASM](https://molab.marimo.io/github/DataBooth/attendance-analyser/blob/main/overview_notebook.py/wasm) |
| Care pack (static) | [molab preview](https://molab.marimo.io/github/DataBooth/attendance-analyser/blob/main/care_pack_notebook.py) |

For full server Python (recommended for DuckDB + CSV), open
[molab.marimo.io](https://molab.marimo.io) and create a notebook from the GitHub URL.

## Care pack (what leaders get)

**Follow up (worth a check-in)**

- Absence after reliability  
- Sharp recent decline  
- Broken attendance streak  
- Returnees after a long gap  

**Connect in**

- New and persistent  
- New but fading  
- Emerging regulars  

**Hospitality health**

- Second-visit / sticky-at-8-weeks funnel  
- Life-cycle scatter (tenure × rate since first)  

**For pastors / ministry leaders:** how the care metrics work in plain language —
[`docs/care-metrics-for-pastors.md`](docs/care-metrics-for-pastors.md).

**Proposal:** excused absences / known away —
[`docs/proposal-excused-absences.md`](docs/proposal-excused-absences.md).

Technical roadmap: [`roadmap.md`](roadmap.md).

## Data format

### Attendance (required)

Long-format CSV with one row per person per week attended:

| week       | person |
|------------|--------|
| 2025-01-05 | C001   |
| 2025-01-05 | C002   |

### Away intervals (optional, Phase 1)

| person | start_week | end_week | reason_code | status | suppress_care_alerts |
|--------|------------|----------|-------------|--------|----------------------|
| C003 | 2026-09-14 | 2026-10-25 | holiday | active | true |

Loaded via `AttendanceAnalyser(attendance.csv, away_csv=away.csv)`.  
See [`docs/proposal-excused-absences.md`](docs/proposal-excused-absences.md).

Synthetic attendance + away files: `just synth`.

## Quick start

```bash
just init
just synth
just test
just edit-care
```

Or without `just`:

```bash
uv sync
uv run python scripts/generate_synthetic_attendance.py
uv run python scripts/smoke_test.py
uv run marimo edit care_pack_notebook.py
```

## Library API (selected)

| Method | Role |
|--------|------|
| `attendance_rates()` / `core_group()` / `weekly_totals()` | Baseline |
| `week_on_week_overlap()` | Stickiness |
| `person_timeline_summary()` | first/last seen, streaks, deltas |
| `absence_watchlist()` / `decline_watchlist()` / `broken_streak_watchlist()` / `returnee_watchlist()` | Follow-up |
| `new_and_persistent()` / `new_and_fading()` / `emerging_regulars()` | Connect-in |
| `second_visit_funnel()` | Hospitality funnel |
| `care_pack(...)` | Bundle of shortlists for the UI |

## Project layout

```text
attendance_logic/          # pure logic package
overview_notebook.py
care_pack_notebook.py
artifacts/synthetic_attendance.csv
roadmap.md
```
