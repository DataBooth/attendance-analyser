# Proposal: Excused absences and “known away” status

**Status:** Phase 1 implemented (away_intervals + care clocks); Phase 2+ still proposed  
**Related:** [`care-metrics-for-pastors.md`](care-metrics-for-pastors.md), [`../roadmap.md`](../roadmap.md)  
**Goal:** Stop treating every missing Sunday the same—so sickness, holidays, and other explained away-time pause care alerts without hiding genuine unexplained drift.

---

## 1. Problem

The care pack currently derives everything from long-format attendance:

```text
week, person
```

A person not listed for a week is indistinguishable from:

- on holiday  
- sick  
- caring for family  
- rostered in another room / other service  
- quietly disengaging  

That creates **false “worth a check-in” signals**, especially on:

- **Broken streak** (one sick Sunday after four present)  
- **Absence after reliability** (fortnight away on leave)  
- **New but fading** (one explained gap after two visits)  
- **Decline** (recent rate depressed by a known trip)

Pastors already “know” many of these cases mentally. We need a small, structured place to record that knowledge so the analysis can respect it.

---

## 2. Design principles

1. **Unexplained absence invites care; explained absence does not chase.**  
2. **Minimal data** — prefer intervals + reason codes over free-text-only workflows.  
3. **Human override always wins** — a “known away” flag must suppress alerts even if attendance is empty.  
4. **Attendance remains source of truth for presence**; away records never invent presence.  
5. **Privacy** — reasons are pastoral-operational, not public; store the least detail needed.  
6. **Backward compatible** — notebooks keep working with attendance-only CSVs; away data is optional.  
7. **Auditability** — every suppressed alert should be explainable (“no alert: holiday 7–28 Sep”).

---

## 3. Proposed data model

### 3.1 Keep existing attendance (unchanged)

**File / table:** `attendance`  
**Grain:** one row per person per week **present**

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `week` | date | yes | Gathering date (typically Sunday) |
| `person` | string | yes | Stable person ID or display key |

Optional later (out of scope here): `service_id`, `source_system`.

---

### 3.2 New: excused / known-away intervals

**File / table:** `away_intervals`  
**Grain:** one row per continuous away period per person

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `person` | string | yes | Same ID space as attendance |
| `start_week` | date | yes | First gathering date covered (inclusive) |
| `end_week` | date | yes | Last gathering date covered (inclusive); may equal `start_week` |
| `reason_code` | enum string | yes | Controlled vocabulary (see §4) |
| `status` | enum string | yes | `scheduled` \| `active` \| `completed` \| `cancelled` (see §5) |
| `suppress_care_alerts` | boolean | yes | Default `true`; rare cases may track away without suppressing |
| `note` | string | no | Short internal note (not for dashboards by default) |
| `recorded_by` | string | no | Who entered it (leader ID or name) |
| `recorded_at` | timestamp | no | When entered |
| `source` | string | no | `manual` \| `elvanto` \| `form` \| `import` |
| `external_id` | string | no | ID in source system for sync |

**Constraints**

- `end_week >= start_week`  
- Prefer aligning `start_week` / `end_week` to actual gathering dates in `attendance`’s calendar  
- Overlapping intervals for the same person are allowed but should be merged or warned on import  
- Open-ended away: set `end_week` far ahead **or** use membership status `away_until` (§3.3) for “until further notice”

**Example**

```csv
person,start_week,end_week,reason_code,status,suppress_care_alerts,note,source
P104,2026-09-07,2026-09-28,holiday,completed,true,Family trip TAS,manual
P088,2026-10-19,2026-10-19,sick,completed,true,,manual
P012,2026-10-01,2026-12-31,work_travel,active,true,FIFO roster,manual
```

---

### 3.3 New (recommended): person status / expectations

**File / table:** `person_status`  
**Grain:** one row per person (current state); optional history table later

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `person` | string | yes | Same ID space |
| `membership_status` | enum | yes | `visitor` \| `new` \| `active` \| `away` \| `seasonal` \| `inactive` |
| `expected_frequency` | enum | no | `weekly` \| `fortnightly` \| `monthly` \| `occasional` \| `unknown` |
| `away_until` | date | no | If set with status `away`, suppress check-ins until this date (inclusive week) |
| `primary_service` | string | no | e.g. `am` / `pm` — future multi-service awareness |
| `household_id` | string | no | Optional roll-up |
| `do_not_chase` | boolean | no | Default `false`; safeguarding / sensitive — never auto-list for outreach |
| `care_notes_ref` | string | no | Link/ID to pastoral notes system (no clinical detail in this DB) |
| `updated_at` | timestamp | no | |
| `updated_by` | string | no | |

**Why both intervals and status?**

| Mechanism | Best for |
|-----------|----------|
| `away_intervals` | Dated trips, sick weeks, finite leave |
| `person_status.away` + `away_until` | Indefinite or administrative “known away” without inventing many interval rows |
| `expected_frequency` | Fortnightly families who should not alert after one missed Sunday |
| `do_not_chase` | Hard stop on lists regardless of pattern |

---

### 3.4 Optional: gathering calendar

**File / table:** `gathering_calendar`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `week` | date | yes | Scheduled gathering |
| `is_gathering` | boolean | yes | `false` for cancelled / combined services |
| `label` | string | no | e.g. `Christmas combined`, `church camp` |

**Use:** weeks with `is_gathering = false` are excluded from “expected” denominators and do not advance unexplained-absence clocks community-wide.

---

## 4. Reason codes (controlled vocabulary)

| `reason_code` | Meaning | Typical `suppress_care_alerts` |
|---------------|---------|--------------------------------|
| `holiday` | Planned travel / vacation | `true` |
| `sick` | Illness | `true` |
| `caring` | Caring for family / others | `true` |
| `work_travel` | Work away | `true` |
| `other_service` | At another service/campus of same church | `true` |
| `serving_elsewhere` | On-site but not on auditorium roll (creche, production) | `true` |
| `study` | Exam block / intensive | `true` |
| `bereavement` | Funeral / grief leave | `true` |
| `approved_leave` | Catch-all pastor-approved finite leave | `true` |
| `seasonal` | Known snowbird / FIFO pattern (prefer status + frequency) | `true` |
| `other` | Explained, unspecified | `true` |
| `unknown` | Placeholder — **should not suppress** unless overridden | `false` |

UI should show friendly labels; storage stays coded.

**Privacy note:** prefer codes over detailed medical or family narrative in `note`.

---

## 5. Status values on intervals

| `status` | Meaning |
|----------|---------|
| `scheduled` | Future leave entered ahead of time |
| `active` | Currently within `[start_week, end_week]` |
| `completed` | Period finished (kept for audit / “back from holiday” context) |
| `cancelled` | Entered in error or plans changed — ignored by analysis |

Analysis uses intervals where:

```text
status IN ('scheduled', 'active', 'completed')
AND suppress_care_alerts = true
AND week overlaps [start_week, end_week]
```

(`scheduled` matters so pre-loaded holidays suppress alerts as soon as those weeks pass without attendance.)

---

## 6. Analysis changes (logical)

### 6.1 New derived concepts

For each person and as-of week `W_max`:

**Explained week**  
Gathering week `W` is explained if:

- exists `away_intervals` row overlapping `W` with suppress flag, or  
- `person_status.membership_status = 'away'` and `W <= away_until`, or  
- `gathering_calendar.is_gathering = false` for `W` (everyone)

**Expected week**  
A week we would have “hoped” to see them, used in rates:

- gathering week, and  
- not explained, and  
- after `first_seen` (for rate-since-first), and  
- consistent with `expected_frequency` (see §6.3)

**Effective last seen (for care)**  
Last week present, **or** if still inside an active explained away period ending in the future, treat “care clock” as paused (do not inflate `weeks_since_last` during explained span).

Concrete definition proposed:

```text
weeks_since_last_unexplained =
  number of expected (unexplained gathering) weeks
  strictly after last presence
  up to W_max
```

Not raw calendar weeks. A three-week holiday then back next Sunday → `weeks_since_last_unexplained = 0` on return week; during holiday → clock frozen or zero for alert purposes.

**Streak for alerts**  
Broken-streak watchlist uses consecutive **expected** weeks present. An explained miss does **not** generate a broken-streak care row (optional: still store statistical streak separately for research).

**Recent rate (care-adjusted)**  

```text
recent_rate_adjusted =
  attendances in last N expected weeks
  / max(count of expected weeks in window, 1)
```

Explained weeks drop out of the denominator so a holiday does not look like “decline.”

**Overall / rate_since_first**  
Same idea optionally applied; or keep raw rates for overview charts and use adjusted rates only inside care lists (recommended split):

| Surface | Rates |
|---------|--------|
| Overview notebook (headcount, heatmap) | Raw attendance |
| Care pack shortlists | Adjusted (expected-week) metrics |
| Pastor guide language | Talk about “unexplained” absence |

---

### 6.2 List-by-list behaviour

| List | Change with away data |
|------|------------------------|
| **Absence after reliability** | Use `weeks_since_last_unexplained ≥ min_weeks_away`; skip if `do_not_chase` or status `away` with valid `away_until` |
| **Decline** | Use adjusted recent vs adjusted baseline (or raw overall vs adjusted recent—document choice); exclude people fully inside active leave |
| **Broken streak** | No alert if the break week(s) are explained |
| **Returnees** | If entire gap explained as `holiday` / `work_travel`, tag reason `Back from planned away` and **deprioritise** or exclude from “re-welcome after drift” list |
| **New and persistent** | Unchanged presence rules; explained gaps don’t wipe “sticky” if still meeting hit counts on expected weeks |
| **New but fading** | Require unexplained weeks away; one sick week after two visits should not list them |
| **Emerging regulars** | Use adjusted rates where helpful |
| **Funnel** | Default unchanged (process KPI); optional footnote when a cohort week was a non-gathering |

---

### 6.3 Expected frequency rules

| `expected_frequency` | Unexplained gap before absence alert (default proposal) |
|----------------------|-----------------------------------------------------------|
| `weekly` | 2 expected gatherings missed |
| `fortnightly` | 2 expected gatherings missed (≈ 3–4 calendar weeks) |
| `monthly` | 2 expected gatherings missed |
| `occasional` / `visitor` | Never on absence-after-reliability; only new/fading style lists |
| `unknown` | Treat as `weekly` but lower priority |

Implementation approach: build a personal expected calendar from gathering weeks + frequency (e.g. fortnightly = every other gathering since first_seen or since a stored anchor).

**Phase 1 shortcut:** only implement weekly + “skip explained weeks,” and store `expected_frequency` for phase 2.

---

### 6.4 API sketch (`AttendanceAnalyser`)

```text
AttendanceAnalyser(
  attendance_csv,
  away_csv=None,
  person_status_csv=None,
  calendar_csv=None,
)

# New / extended
explained_weeks(person) -> set[date]
is_known_away(person, as_of=None) -> bool
person_timeline_summary(..., adjust_for_away=True)
absence_watchlist(...)   # uses unexplained clocks
decline_watchlist(...)
broken_streak_watchlist(...)
care_pack(...)           # pass-through flags + optional column: away_suppressed

# Diagnostics for pastors/admins
away_suppression_report() ->
  person, list_name, would_have_alerted, suppressed_by (interval id / status)
```

Add output columns on care tables when away data present:

| Column | Meaning |
|--------|---------|
| `weeks_since_last_unexplained` | Care clock |
| `explained_weeks_recent` | Count of explained weeks in recent window |
| `known_away_now` | Boolean |
| `suppression_note` | Short machine reason |

---

## 7. UI / notebook implications

**Care pack sliders (add):**

- Toggle: **Respect known away** (default on)  
- Toggle: **Show suppressed rows** (admin debug; default off)  
- Optional filter: reason codes included in suppression  

**New small admin section or separate notebook:**

- Table of active `away_intervals`  
- People with `membership_status = away`  
- Warnings: attendance recorded **during** an away interval (data conflict—keep attendance, flag interval)

**Pastor-facing copy** (update care guide):

> If someone is on the absence list, it means we have **unexplained** missed gatherings relative to what we expected—not that they failed a test.

---

## 8. Source systems and capture workflow

### Phase A — Manual CSV (fastest)

1. Export attendance as now.  
2. Maintain `away_intervals.csv` + optional `person_status.csv` in a controlled folder or Sheet → CSV.  
3. Load both paths into the analyser.

### Phase B — Form

Short form: person, from Sunday, to Sunday, reason.  
Writes to Sheet/DB → CSV or API.

### Phase C — ChMS sync (Elvanto etc.)

Map native “out of town” / absence fields into `away_intervals`.  
Map member status to `person_status`.

### Operational rhythm

| When | Action |
|------|--------|
| Before leave | Enter `scheduled` interval |
| During leave | Status `active` (auto from dates) |
| After return | Interval `completed`; if they attend, returnee logic may soft-tag |
| Weekly care meeting | Run pack with “Respect known away” on; only unexplained names |

---

## 9. Synthetic data and testing

Extend `scripts/generate_synthetic_attendance.py` (or companion script) to emit:

- `artifacts/synthetic_away_intervals.csv`  
- `artifacts/synthetic_person_status.csv`  

**Fixtures to prove behaviour:**

| Persona | Setup | Expect |
|---------|--------|--------|
| Core + 3-week holiday | interval `holiday` | Not on absence list during/after if returned |
| Core + 1 sick after streak | interval `sick` | Not on broken-streak list |
| Core + 3 unexplained | no interval | On absence list |
| Fortnightly active | `expected_frequency=fortnightly` | No alert after single calendar miss (phase 2) |
| `do_not_chase=true` + long gap | status flag | Never on outreach lists |
| Attend during away | conflict | Warning row; attendance wins |

Smoke tests: assert suppression and non-suppression cases.

---

## 10. Privacy, safeguarding, and governance

1. **Access control:** away reasons and `do_not_chase` are pastoral-care sensitive — same or tighter access than attendance.  
2. **Retention:** completed intervals retain for audit (e.g. 12–24 months) then archive.  
3. **`note` field:** discourage medical detail; codes first.  
4. **`do_not_chase`:** hard exclusion from care_pack outreach lists; still visible to authorised pastors in a separate “sensitive” view if ever built.  
5. **Demo/molab:** synthetic IDs only; never publish real away notes.  
6. **Consent / policy:** align with church privacy policy for pastoral records.

---

## 11. Implementation plan

### Phase 1 — MVP — **done**

- Schema: `away_intervals` only (+ loader) — `AttendanceAnalyser(..., away_csv=)`  
- Reason codes + `suppress_care_alerts`  
- Adjusted `weeks_since_last_unexplained`, `recent_rate_adjusted`, `known_away_now`  
- Wired into absence, broken streak, new fading, decline; returnees deprioritise fully explained gaps  
- Care pack toggle **Respect known away** + away intervals table + `suppression_note`  
- Synthetic `artifacts/synthetic_away_intervals.csv` via `just synth`  
- Smoke tests for C003 suppressed / C027 unexplained  

**Still open for Phase 1 polish:** pastor-facing copy tweaks; admin entry UI.

### Phase 2 — Status and frequency

- `person_status` (`away`, `away_until`, `expected_frequency`, `do_not_chase`)  
- Frequency-aware expected weeks  
- Returnee deprioritisation when gap fully explained  

### Phase 3 — Calendar and integrations

- `gathering_calendar`  
- Household roll-up  
- Elvanto/form import  
- Admin UI for entry  

---

## 12. Open decisions (need owner input)

1. **Denomination of “week”:** always Sunday date of service, or Mon–Sun week key?  
2. **Decline baseline:** adjusted overall vs adjusted rate-since-first vs raw overall?  
3. **Return after long explained holiday:** exclude from returnees list, or keep with different suggested action (“Welcome back from leave”)?  
4. **Serving elsewhere:** is that an away interval or a separate `present_elsewhere` attendance channel?  
5. **Who may enter away data?** pastors only vs small-group leaders vs self-serve form?  
6. **Fortnightly detection:** manual `expected_frequency` only, or auto-infer from history? (Manual first is safer.)

---

## 13. Success criteria

- Measurable drop in “obvious false” absence/streak alerts when holidays are entered  
- Leaders can enter a trip in &lt; 30 seconds  
- Care pack still runs if only attendance CSV is provided  
- Every suppressed alert has a transparent reason for audit  
- Pastor guide updated so elders trust unexplained vs explained language  

---

## 14. Summary recommendation

**Adopt two layers:**

1. **`away_intervals`** — dated excused absence with reason codes (MVP).  
2. **`person_status`** — standing `away` / frequency / `do_not_chase` (phase 2).  

**Redefine care clocks on unexplained expected gatherings**, leave overview headcount charts on raw attendance, and keep humans in charge of contact.

---

## 15. Appendix — example file layouts

**`artifacts/away_intervals.csv`**

```csv
person,start_week,end_week,reason_code,status,suppress_care_alerts,note,recorded_by,source
C003,2026-09-14,2026-10-05,holiday,completed,true,,pastor_ann,manual
C011,2026-10-19,2026-10-19,sick,completed,true,,pastor_ann,manual
M021,2026-08-01,2026-11-30,work_travel,active,true,FIFO,pastor_ann,manual
```

**`artifacts/person_status.csv`**

```csv
person,membership_status,expected_frequency,away_until,do_not_chase,updated_at
C003,active,weekly,,false,2026-10-01T10:00:00
M040,active,fortnightly,,false,2026-10-01T10:00:00
P999,away,weekly,2026-12-15,false,2026-10-01T10:00:00
P777,active,weekly,,true,2026-10-01T10:00:00
```

---

*End of draft. Next step after approval: Phase 1 implementation in `attendance_logic` + care pack toggle + synthetic fixtures.*
