# Care pack metrics — a note for pastors and ministry leaders

This note explains **what the care pack is measuring**, **why it matters pastorally**, and **how to use the lists without treating people as data points**.

You do not need to understand databases or charts to use this well. Think of the tool as a **weekly memory aid**: it notices patterns in attendance that busy teams often miss, then hands you shortlists with a plain-language reason and a suggested kind of contact.

---

## 1. What this tool is (and is not)

### It is

- A **prompt for human care**, based only on who was recorded as present each week
- A way to answer two practical questions each week:
  1. Who might need a **gentle check-in**?
  2. Who is **new and sticking**, so we should **connect them in** before the window closes?
- Adjustable — sliders change how sensitive the lists are

### It is not

- A judgement that someone is “backsliding,” “disengaged,” or “in crisis”
- A substitute for knowing your people, pastoral notes, or the Holy Spirit’s prompting
- Proof of spiritual health (attendance is only one weak signal among many)
- Permission to message people automatically or publish absence leaderboards

**Golden rule:** if the list surprises you, get curious — don’t get accusatory.

---

## 2. The only raw facts we use

For each person the system only knows:

| Fact | Meaning in plain English |
|------|---------------------------|
| **Week** | The Sunday (or gathering date) they were marked present |
| **Person** | Their identifier (name or ID from your roll / Elvanto export) |

Everything else is **derived** from those two columns: how often they come, when they first appeared, when we last saw them, and whether their recent pattern differs from their longer-term pattern.

We do **not** currently use age, family links, serving roles, giving, small groups, or pastoral notes — unless you add those later. That keeps the logic simple and honest about its limits.

---

## 3. Building blocks (the “metrics” behind the lists)

These appear as columns in tables. You can ignore the numbers day-to-day; the **list name + reason** is enough. The definitions help when you want to trust (or challenge) a result.

### 3.1 Overall attendance rate

**What it is:**  
Of all the weeks in the dataset, what fraction was this person present?

Example: present 45 of 90 weeks → overall rate **50%**.

**Pastoral reading:**  
A rough sense of “how much a regular are they?” over the whole period you loaded. Someone at 80%+ is usually part of the backbone of the gathering. Someone at 10% may be occasional, visiting family, or only connected lightly.

**Caution:** A low overall rate is normal for people who **joined recently** (they weren’t in the room for earlier weeks). For newer people we prefer **rate since first seen** (below).

### 3.2 Recent attendance rate

**What it is:**  
Of the last *N* weeks (default **12**, slider: “Recent window”), what fraction were they present?

Example: 3 of the last 12 weeks → recent rate **25%**.

**Pastoral reading:**  
“What does life look like **now**?” More useful than overall rate when patterns are changing.

### 3.3 Delta (recent − overall)

**What it is:**  
Recent rate minus overall rate.

- **Positive delta** → coming *more* than their long-run average (rising)
- **Negative delta** → coming *less* than their long-run average (cooling)

Example: overall 70%, recent 40% → delta **−30 percentage points** (a sharp cooling).

**Pastoral reading:**  
This is the “something has shifted” signal. It often flags drift **before** total disappearance.

### 3.4 First seen / last seen

**What they are:**  
- **First seen:** first week they appear in the data  
- **Last seen:** most recent week they appear  

**Pastoral reading:**  
First seen ≈ “when did this person enter our story (in this dataset)?”  
Last seen ≈ “when did we last have a face-to-face chance to notice them?”

### 3.5 Weeks since last

**What it is:**  
How many weeks between their last attendance and the latest week in the data.

Example: last seen two Sundays ago → **2**.

**Pastoral reading:**  
The simplest absence clock. Defaults often treat **2+ weeks** away (for people who used to be regular) as worth a check-in. You can raise this to 3 if your culture is less weekly.

### 3.6 Tenure (weeks since first seen)

**What it is:**  
How long they have been “in view” since their first attendance.

**Pastoral reading:**  
Helps separate **brand-new** people from long-timers. A 10-week absence means something different for a 2-year regular than for someone who only ever came twice.

### 3.7 Rate since first seen

**What it is:**  
Attendances ÷ weeks available **since they first appeared** (not since the start of the whole dataset).

**Pastoral reading:**  
The fair score for newcomers and mid-joiners. “Since they arrived, how consistently have they come?”

### 3.8 Streaks

**What they are:**  
- **Longest streak:** longest run of consecutive weeks present  
- **Streak at last seen:** length of the consecutive run that ended on their last attendance  

**Pastoral reading:**  
Streaks capture rhythm. Someone who came **six weeks in a row** and then missed is a different pastoral moment than someone who always came every other week.

### 3.9 Core threshold / core group

**What it is:**  
People whose **overall rate** is at or above a slider value (default **60%**).

**Pastoral reading:**  
Not a spiritual elite — a statistical “usually here” band. When **core people** go quiet, the tool prioritises them more heavily, because the contrast with their normal pattern is larger and the relational opportunity is often clearer.

### 3.10 Priority score

**What it is:**  
An internal ranking number so the most urgent rows float to the top of each list. It combines a few of the building blocks (for example, longer absence + higher overall rate → higher priority on the absence list).

**Pastoral reading:**  
Use it only as a **sort order**, not as a grade out of 10 for a person’s worth or need. Two people with similar scores may need completely different approaches.

### 3.11 Suggested action

**What it is:**  
A short label for the *kind* of contact, not a script you must use:

| Label | Tone |
|-------|------|
| Gentle check-in | Warm, no pressure; “we noticed and we care” |
| Light-touch check-in | Softer still; often for people still attending sometimes |
| Timely, specific check-in | Reference the recent rhythm (“after several weeks with us…”) |
| Warm re-welcome | Returning after a long gap — not a first-timer welcome |
| Connect into community | New and sticking — introductions, groups, next steps |
| Early hospitality follow-up | New but fading — “how was your visit?” energy |
| Thank and invite deeper | Emerging regulars — gratitude + belonging |

---

## 4. The care pack lists (what you actually work from)

Open **`care_pack_notebook.py`** (`just edit-care`). At the top, sliders set sensitivity. Below that, two families of lists.

### A. Follow up — “worth a check-in”

#### 1) Absence after reliability

**In one sentence:**  
People who **used to come often** and have now been **away for at least a couple of weeks**.

**Default logic (approximate):**  
- Overall rate high enough to count as “regular” (linked to your core threshold; often around 45–50%+)  
- Weeks since last ≥ **2** (slider)

**Why pastors care:**  
This is the classic “we haven’t seen you” list. It surfaces backbone people whose absence can otherwise hide inside a large room.

**Good pastoral instincts:**  
- Assume travel, illness, caring responsibilities, or roster elsewhere first  
- Prefer a personal message from someone who already knows them  
- One caring contact beats five generic “we missed you” blasts  

**Poor use:**  
Calling them “lapsed” in a public meeting or chasing them as a membership problem.

---

#### 2) Sharp recent decline

**In one sentence:**  
People who are **still around sometimes**, but much **less than before**.

**Default logic (approximate):**  
- Recent rate well below overall rate (delta about **−20 points** or worse)  
- Enough history (about **8+ weeks** since first seen) so it isn’t random noise  
- Not already in the “fully away” absence bucket  

**Why pastors care:**  
Drift often shows up as thinning before vanishing. This list is an early warning with a lighter touch.

**Good pastoral instincts:**  
- “How are you going?” not “Why aren’t you coming?”  
- May connect to load, disappointment, family stress, or simply a busy season  

---

#### 3) Broken attendance streak

**In one sentence:**  
People who had a **clear run of consecutive weeks**, then **missed**.

**Default logic (approximate):**  
- Streak of about **4+** weeks ending at their last visit  
- At least one week away since  

**Why pastors care:**  
The contact can be **specific and kind**: “We loved having you those weeks running — just wanted you to know you’re on our heart.” Specificity feels human; generic absence mail feels bureaucratic.

---

#### 4) Returnees (re-welcome)

**In one sentence:**  
People with **history here**, a **long gap**, then **one or two recent appearances**.

**Default logic (approximate):**  
- Present in the last 1–2 weeks  
- Gap since previous chapter of attendance about **8+ weeks**  

**Why pastors care:**  
Returning is vulnerable. Treating a returnee like a brand-new visitor (“Are you new?”) can sting. Treating them like they never left can also miss the moment.

**Good pastoral instincts:**  
- “It’s really good to see you again.”  
- No interrogation about the gap unless they open it  
- Offer a simple next step if appropriate (coffee, group, serving interest)  

---

### B. Connect in — “new and becoming part of us”

#### 5) New and persistent (“new and sticky”)

**In one sentence:**  
People who **started recently** and are **coming with real consistency**.

**Default logic (approximate):**  
- First seen within about the last **12 weeks** (slider: New window)  
- Enough consistency (e.g. several attendances and/or solid rate since first seen)  
- Still showing up in the **last few weeks**  

**Why pastors care:**  
This is the golden hospitality window. People who are forming a habit are signalling openness. If nobody names them, invites them, or introduces them, the habit can plateau as “anonymous regular” — or fade.

**Good pastoral instincts:**  
- Assign a **named welcomer** or couple (not “someone should…”)  
- Invite to something smaller than the main gathering (morning tea with purpose, group, course, serving taster)  
- Learn one real fact about them (names of kids, suburb, how they found you)  

---

#### 6) New but fading

**In one sentence:**  
People who **started recently**, came **only a little**, and have **gone quiet**.

**Default logic (approximate):**  
- First seen within the new window  
- Only a few attendances  
- Away for a couple of weeks or more  

**Why pastors care:**  
This is usually a **hospitality / fit / logistics** conversation, not the same tone as checking on a 10-year regular. Maybe parking was hard, they didn’t meet anyone, the service length surprised them, or life simply got full after a good first impression.

**Good pastoral instincts:**  
- Short, low-pressure: “We loved meeting you — how did you find it?”  
- One human reply is success; don’t over-shepherd a thin connection  

---

#### 7) Emerging regulars

**In one sentence:**  
People past the brand-new window who have **settled into a strong pattern** — time to **thank** them and **invite deeper belonging**, not only “welcome”.

**Default logic (approximate):**  
- First seen roughly **8–26 weeks** ago  
- Strong rate since first seen **and** strong recent rate  

**Why pastors care:**  
Many churches over-invest in week 1 and under-invest in month 4. Emerging regulars are ready for identity language: “You’re part of us,” groups, serving, friendship, prayer care.

---

## 5. Community health charts (not person lists)

These help elders/staff see **system** issues, not only individuals.

### Second-visit funnel

For people who first came in a given week (a “cohort”), we later ask:

1. **Did they return within about 4 weeks?**  
2. **By 8 weeks, had they come about 4+ times?** (“sticky”)

**Pastoral reading:**  
If first-time numbers are fine but return rates fall, the issue is often **welcome quality, clarity of next steps, or midweek connection** — not “people today are flaky.” Fix processes, not just persons.

### Life-cycle map (scatter)

Each person is a point:

- **Left → right:** how long since first seen  
- **Low → high:** how consistently they’ve come since then  
- **Colour:** how long since last seen (hotter = longer away)

**Pastoral reading:**  
A quick landscape: dense cloud of long-tenure high-rate people (core), a spray of new people on the left, and outliers who are long-tenure but cooling.

### Week-on-week overlap (overview notebook)

- **Retention:** of last week’s people, what share came again?  
- **Jaccard:** similarity of the two weeks’ congregations (shared ÷ everyone who came either week)  
- **Shared / newcomers / leavers:** the churn underneath a stable headcount  

**Pastoral reading:**  
Headcount can look “fine” while the cast of characters turns over. High churn with flat totals still means lots of people slipping through without being known.

---

## 6. How to run a healthy weekly rhythm

A simple 20-minute staff or pastoral care rhythm:

1. **Open the care pack** after the latest attendance is loaded.  
2. **Scan Absence + Decline first** (follow up).  
3. **Scan New & persistent** (connect in) — assign real names to real people for contact.  
4. **Glance at New & fading** for one or two hospitality touches.  
5. **Note Returnees** so Sunday welcome doesn’t mishandle them.  
6. **Write nothing in the tool that you wouldn’t say to their face** in love.  
7. **Mark privately** (in your own notes) who was contacted, so you don’t spam.

If a list is too long: raise “min weeks away”, raise core threshold, or lower Top N.  
If a list is empty: loosen sliders slightly — or celebrate that patterns look steady.

---

## 7. Interpreting common situations

| What you see | Possible real-world meaning | Careful response |
|--------------|----------------------------|------------------|
| Core person, 3 weeks away | Holiday, illness, conflict, caring load, quiet exit | Personal check-in from someone who knows them |
| Negative delta, still attending | Cooling interest, burnout, family change | Light touch; listen |
| Broken 6-week streak | Rhythm interrupted | Specific, warm notice |
| New sticky 5 of last 7 weeks | Openness / hunger for belonging | Accelerate connection |
| New fading after 1–2 visits | Weak first impression or life noise | Hospitality follow-up, not heavy discipleship chase |
| Return after 6 months | Courage to come back | Re-welcome; no guilt |
| Funnel return rate dropping | Process problem | Review welcome pathway |
| Headcount up, retention down | Growth with churn | Resource welcome & integration |

---

## 8. Defaults (so “the computer said” is inspectable)

These are starting points in the care pack, and can be changed with sliders or by your technical helper:

| Setting | Typical default | Effect of increasing it |
|---------|-----------------|-------------------------|
| Core threshold | 60% | Smaller “core”; absence list focuses on stronger regulars |
| Recent window | 12 weeks | Smoother recent rate; slower to react |
| Min weeks away | 2 | Fewer absence/fading alerts; only longer gaps |
| New window | 12 weeks | Broader “new” definition |
| Top N | 15 | Longer shortlists on screen |

**Absence list** uses a “regular enough” bar near the core threshold (slightly looser so solid fortnightly people aren’t ignored).  
**Decline** looks for roughly a **20 point** drop in recent vs overall.  
**Broken streak** starts around **4** consecutive weeks.  
**Returnee gap** starts around **8** weeks.  
**Sticky-at-8-weeks** means about **4** attendances in the first 8 weeks after first visit.

If your main gathering is truly fortnightly for many families, ask for defaults to be tuned — weekly assumptions will over-alert.

---

## 8b. Holidays, sickness, and other “known away” time

**Phase 1 is live.** You can load an **away intervals** CSV so excused weeks
(holiday, sick, work travel, …) **pause check-in clocks**.

In the care pack notebook:

1. Ensure `artifacts/synthetic_away_intervals.csv` (or your real away file) is present.  
2. Leave **Respect known away** switched **on** (default).  
3. Review the **Known away / excused intervals** table.  
4. Absence / broken streak / new fading use **unexplained** weeks only.  
5. Toggle the switch **off** to see the old “raw calendar gap” behaviour.

Details and file layout: [`proposal-excused-absences.md`](proposal-excused-absences.md).

If someone is still on a list with the switch on, treat that as **unexplained**
relative to what we expected—not a moral failure.

## 9. Ethics, privacy, and tone

1. **Language:** prefer “worth a check-in” and “connect in” over “at risk,” “disengaged,” or “problem people.”  
2. **Access:** real names belong on a need-to-know basis (pastors, authorised carers). Demo/synthetic mode uses codes like `C014`.  
3. **Storage:** treat attendance exports like pastoral records.  
4. **Bias check:** the tool only sees recorded attendance. People who serve in the creche, watch online, or attend another service may look “absent” when they are faithful. Always allow human override.  
5. **No automation without review:** do not auto-SMS absence lists without a person choosing each contact.  
6. **Humility:** God knows people; spreadsheets do not. The aim is love that notices, not management that surveils.

---

## 10. A short theology of noticing

Scripture’s picture of shepherding includes **knowing** the flock and **seeking** the one who is missing — not to scold, but to restore and protect (see e.g. Ezekiel 34; Luke 15; Acts 20:28; 1 Peter 5:2–3).

In a room of 100–140 faces, noticing is a **structural problem**, not only a virtue problem. Tools like this don’t create love; they reduce the chance that love never gets a name and a week attached to it.

Use the lists to ask better questions:

- Who have we stopped seeing?  
- Who is new and ready for friendship?  
- Where is our welcome pathway leaking?

Then close the laptop and make the call, send the message, or stand with someone after the service.

---

## 11. Where to click

| Need | Open |
|------|------|
| This week’s shortlists | `care_pack_notebook.py` (`just edit-care`) |
| Headcount, core, overlap, heatmap | `overview_notebook.py` (`just edit`) |
| Technical roadmap | `roadmap.md` |
| This guide | `docs/care-metrics-for-pastors.md` |

---

*If something on a list consistently feels wrong for your context, that’s useful feedback — the thresholds should serve your people, not the other way around.*
