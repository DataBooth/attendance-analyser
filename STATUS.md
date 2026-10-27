# Project status — attendance-analyser

**Parked:** 27 Oct 2026  
**Repo:** https://github.com/DataBooth/attendance-analyser  
**Branch:** `main` @ `2551e3d` (clean working tree)  
**Default workflow note:** recent work was pushed straight to `main` (no open PRs). Prefer feature branches + PRs for the next slice of work.

---

## What this is

Marimo + DuckDB + Polars toolkit for **weekly gathering attendance**:

1. **Overview** — rates, core group, weekly totals, week-on-week overlap, heatmap, recency  
2. **Care pack** — pastoral shortlists (check-in + connect-in) with optional **excused absence** handling  

Logic lives in `attendance_logic/`; notebooks are thin UI.

---

## Done

| Area | Status |
|------|--------|
| `AttendanceAnalyser` package | Done |
| Overview notebook | `overview_notebook.py` |
| Care pack notebook | `care_pack_notebook.py` |
| Synthetic attendance (~100 mid-2025 → ~140 latest; Δ≤15) | Done |
| Week-on-week overlap | Done |
| Care lists (absence, decline, streak, returnees, new sticky/fading, emerging, funnel) | Done |
| Pastor-facing metrics guide | `docs/care-metrics-for-pastors.md` |
| Excused-absence proposal | `docs/proposal-excused-absences.md` |
| **Phase 1 excused absences** (`away_intervals`, unexplained clocks, care-pack toggle) | Done |
| Synthetic away fixtures | `artifacts/synthetic_away_intervals.csv` |
| Smoke tests including C003 suppressed / C027 unexplained | `just test` |
| molab links / session snapshot (overview) | Earlier commit; may need refresh after renames |
| uv + justfile cross-platform recipes | Done |

### Phase 1 behaviour (quick reminder)

- Load: `AttendanceAnalyser(attendance.csv, away_csv=away.csv)`  
- Care pack switch: **Respect known away** (default on)  
- Explained weeks pause `weeks_since_last_unexplained`  
- Absence / broken streak / new fading / decline use unexplained logic when switch on  
- Attendance-only still works if no away file  

---

## Not done / next

| Item | Notes |
|------|--------|
| **Phase 2** | `person_status` (away_until, expected_frequency, do_not_chase) |
| **Phase 3** | Gathering calendar, household, Elvanto/form import, admin entry UI |
| Real attendance import docs | Elvanto export → long-format CSV |
| PR workflow | Use branches for Phase 2+ |
| GitHub Release | Optional tag (e.g. v0.2.0) for Phase 1 snapshot |
| molab session for care pack | `just session` if static previews wanted |
| Module split polish | Already in `attendance_logic/`; further packaging optional |

Open decisions for Phase 2 are listed in `docs/proposal-excused-absences.md` §12.

---

## How to run (when you return)

```bash
cd /Users/mjboothaus/code/github/databooth/attendance-analyser
just init
just synth      # regenerates attendance + away CSVs
just test
just edit       # overview
just edit-care  # pastoral care pack
```

**Docs to reread first**

1. `docs/care-metrics-for-pastors.md` — how leaders should use lists  
2. `docs/proposal-excused-absences.md` — Phase 1 done; Phase 2+ design  
3. `roadmap.md` — longer product roadmap  

---

## Key paths

```text
attendance_logic/analyser.py          # core analysis + Phase 1 away
overview_notebook.py
care_pack_notebook.py
artifacts/synthetic_attendance.csv
artifacts/synthetic_away_intervals.csv
docs/care-metrics-for-pastors.md
docs/proposal-excused-absences.md
roadmap.md
STATUS.md                             # this file
```

---

## Suggested first task when un-parking

Implement **Phase 2** on a branch, e.g. `feature/person-status-away`:

- `person_status.csv` loader  
- `away_until` / `expected_frequency` / `do_not_chase`  
- Wire into care clocks  
- Open a PR into `main`  

---

*Working tree was clean at park time. No local uncommitted work expected.*
