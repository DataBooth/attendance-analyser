# Roadmap — pastoral insight from attendance

This roadmap prioritises analyses that help a community **notice people early**:
those who may need a gentle check-in, and those who are new and sticking around
and should be **welcomed and connected in**.

It builds on the current notebook (`AttendanceAnalyser`: rates, core group,
recency, week-on-week overlap) without assuming extra data sources. Later phases
can layer Elvanto/CRM attributes when available.

**Design principles**

- Prefer **actionable shortlists** over dashboards alone (name + reason + suggested action).
- Keep logic in `AttendanceAnalyser`; Marimo cells only render controls and tables/charts.
- Tune thresholds with UI sliders; document defaults that match a ~weekly gathering.
- Treat outputs as **prompts for human care**, not automated judgements.
- Privacy: stable anonymisation tokens for demos; real IDs only in controlled environments.

---

## North-star questions

1. **Who should we follow up this week** because their pattern suggests they might
   not be OK, or are drifting away?
2. **Who is new and becoming persistent**, so we should connect them into
   relationships, teams, or next steps before the “newness” window closes?
3. **Who is quietly reliable**, so we can thank them and avoid only reacting to problems?

---

## Phase 0 — Foundations (done / nearly done)

| Capability | Status | Why it matters |
|------------|--------|----------------|
| Attendance rates + core group | Done | Baseline “who usually shows up” |
| Recent vs overall rate | Done | Rising / falling signal |
| Week-on-week overlap | Done | Community stickiness, not just headcount |
| Synthetic long-format data | Done | Safe iteration without PII |

**Small gaps to close before pastoral lists**

- Person-level **first_seen** / **last_seen** / **weeks_since_last**
- Gap detection (consecutive misses after a streak)
- Explicit “lifecycle” labels derived only from attendance

---

## Phase 1 — Follow-up shortlists (highest insight)

Goal: each week produce a ranked **“check in”** list with transparent reasons.

### 1.1 Absence after reliability (priority)

**Signal:** historically regular people who have gone quiet.

Suggested rules (defaults tunable):

- Overall rate ≥ core threshold (e.g. 0.6) **or** attended ≥ *N* of last *M* weeks historically
- **Weeks since last attendance** ≥ 2 (or 3)
- Optionally: last absence streak is the longest in their history

**Output columns:** `person`, `last_seen`, `weeks_since_last`, `overall_rate`,
`recent_rate`, `prior_streak_weeks`, `reason`, `priority_score`

**Pastoral use:** “We noticed we haven’t seen you — everything OK?”

### 1.2 Sharp decline (still attending sometimes)

**Signal:** still appearing occasionally, but rate has dropped.

- Large negative `delta` (recent − overall), e.g. ≤ −0.25
- Minimum history so noise is low (e.g. ≥ 8 weeks since first_seen)
- Not already on the “fully absent” list

**Pastoral use:** lighter touch than full absence; often catches drift earlier.

### 1.3 Broken streak

**Signal:** longest recent consecutive attendance broken.

- Had a streak of ≥ *K* weeks (e.g. 4+), then missed the latest week(s)
- Rank by streak length × how core they were

**Pastoral use:** timely, specific (“after several weeks in a row…”).

### 1.4 Returnees who may need re-welcome

**Signal:** long gap, then one or two recent attendances.

- Gap ≥ *G* weeks (e.g. 8+), then present in last 1–2 weeks
- Distinguish from brand-new people via earlier history

**Pastoral use:** warm re-connection without treating them as first-timers.

### 1.5 Composite “care score” (optional)

Weighted blend for ranking only (show component reasons in the UI):

| Component | Direction |
|-----------|-----------|
| Weeks since last | Higher → more urgent |
| Decline delta | More negative → more urgent |
| Broken long streak | Higher → more urgent |
| Core membership | Core misses weighted higher than fringe |

Export: `care_watchlist(as_of_week, ...)` → Polars table + Plotly strip/bar of scores.

---

## Phase 2 — New and persistent (connect-in shortlists)

Goal: spot people in the **onboarding window** who are forming a habit, before
they are absorbed into the anonymous crowd — or before they fade after a strong start.

### 2.1 First-seen cohort

**Signal:** first attendance within last *W* weeks (e.g. 8 or 12).

Metrics per person:

- `first_seen`, `attendances_since_first`, `possible_weeks_since_first`
- `early_rate` = attendances / possible weeks since first
- `last_seen`, whether present in the most recent week

### 2.2 “New and sticky” (connect in)

**Signal:** new *and* consistent.

Defaults to explore:

- `first_seen` within last 12 weeks
- Attended ≥ 3 of possible weeks **or** early_rate ≥ 0.5
- Present in ≥ 2 of the last 4 weeks
- Not yet in long-term core (or mark separately once they graduate)

**Output:** ranked welcome/connect list with `suggested_action`  
e.g. “Invite to morning tea”, “Introduce to small group leader”, “Add to roster interest”.

### 2.3 “New but fading” (early follow-up)

**Signal:** started recently, then stopped.

- `first_seen` within last 12 weeks
- Attended 1–2 times only, **or** early burst then ≥ 3 weeks absence
- `last_seen` not in the latest week

**Pastoral use:** different script from long-term core absence — often logistics,
fit, or first-impression issues.

### 2.4 Graduation: new → emerging regular

**Signal:** crossed from new cohort into sustained pattern.

- first_seen 8–26 weeks ago
- early_rate high and recent_rate still high
- Now eligible for “thank / invite deeper” rather than “first welcome”

### 2.5 Second-week conversion (funnel)

Community-level funnel (not only person lists):

| Stage | Definition |
|-------|------------|
| First visit | first_seen = week *t* |
| Returned ≤ 4 weeks | second attendance within 4 weeks |
| Sticky at 8 weeks | ≥ 4 attendances in first 8 possible weeks |

Chart week-by-week conversion rates. Drops here inform hospitality process, not only individuals.

---

## Phase 3 — Pattern & context (richer insight)

### 3.1 Seasonal and calendar effects

- Flag school holidays, public holidays, known event weeks
- Avoid false “crisis” alerts when whole-community attendance dips

### 3.2 Peer / co-attendance (optional, careful)

- People who often attend the **same weeks** (simple co-occurrence)
- Use only to suggest **who might naturally introduce a new sticky person**
- Do **not** infer private relationships; keep opt-in and coarse

### 3.3 Household / family roll-up (needs extra data)

- If person→household mapping exists, surface household-level absence
- One contact may cover several people

### 3.4 Service / event type split (Elvanto-style)

- Extend placeholder `add_service_filter`
- Core and care lists per service (morning vs evening, etc.)

### 3.5 Capacity and team health

- Over-reliance on a tiny core (Gini or top-decile share of attendance-weeks)
- “Core fatigue” proxy: core members with rising absence

---

## Phase 4 — Product & workflow

| Item | Notes |
|------|--------|
| **Weekly care pack** | One markdown/PDF or CSV: Top 10 check-ins + Top 10 connect-ins |
| **Assignable UI** | Optional “acknowledged this week” state (local or sheet) to avoid repeat nagging |
| **Threshold presets** | “Conservative / Balanced / Sensitive” slider sets |
| **Anonymised demo mode** | Token map; real names only behind explicit load of private CSV |
| **Tests** | Golden fixtures for decline, broken streak, new-sticky, new-fading |
| **Module split** | Move `AttendanceAnalyser` → `src/attendance_logic/` for reuse outside Marimo |
| **Elvanto import** | Document export columns → long-format `week, person` (+ optional attrs) |

---

## Suggested method API (future)

Keep returns as Polars DataFrames unless noted.

```text
person_timeline_summary()
  → person, first_seen, last_seen, weeks_attended, overall_rate,
    weeks_since_last, longest_streak, current_streak

absence_watchlist(min_overall, min_weeks_away, ...)
decline_watchlist(recent_weeks, max_delta, min_history_weeks, ...)
broken_streak_watchlist(min_streak, ...)
returnee_watchlist(min_gap_weeks, recent_window, ...)

newcomers(within_weeks)
new_and_persistent(within_weeks, min_early_rate, min_recent_hits, ...)
new_and_fading(within_weeks, ...)
emerging_regulars(min_tenure_weeks, max_tenure_weeks, ...)

second_visit_funnel(by_cohort_week)
care_pack(as_of=None)  # convenience bundle of shortlists + summary stats
```

---

## Implementation order (recommended)

1. **Person timeline summary** — unlocks almost everything  
2. **Absence watchlist** + **decline watchlist** — follow-up value immediately  
3. **New and persistent** + **new and fading** — connect-in value immediately  
4. Notebook section: **This week’s care pack** (two tables + copyable summary)  
5. Broken streaks + returnees  
6. Second-visit funnel chart  
7. Seasonal flags, household roll-up, co-attendance (as data allows)  
8. Export/automation (CSV email, scheduled run)

---

## Success metrics (for the tool, not the people)

- Time for a leader to get a **credible shortlist** &lt; 2 minutes after data refresh  
- Each listed person has a **human-readable reason**  
- False alarms drop after seasonal/holiday handling  
- “New and sticky” list is short enough to act on weekly (target: order of 5–15 names for ~100/week gatherings)  
- Privacy defaults safe for screenshots and molab demos  

---

## Ethics and tone

- Language in the UI: **“worth a check-in”**, not “at risk” or “disengaged” as labels on people  
- Absence ≠ problem (travel, illness, roster elsewhere)  
- Prefer **opt-in pastoral workflows**; avoid public leaderboards of absence  
- Log access if real member data is used in shared environments  

---

## Out of scope (for now)

- Predictive ML black boxes without explainable features  
- Automated messages to members without human review  
- Replacing CRM/pastoral notes systems  

---

## Open decisions

- Default **weeks away** before check-in (2 vs 3) for a weekly event  
- Whether “new” is calendar weeks since first_seen or first *N* attendances  
- How aggressively to weight **core** vs **everyone** on the care list  
- Whether connect-in lists should hide people already flagged in a team roster (needs extra data)

When ready to implement, start with Phase 1.1–1.2 and Phase 2.2–2.3 in the
existing class/notebook split, then add a single **Care pack** Marimo section
that leaders can screenshot or export each week.
