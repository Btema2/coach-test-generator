# Sectioned Exam with Timing Rules

**Date:** 2026-06-15
**Status:** Approved
**Feedback source:** ICF coach review of live mock exam

## Problem

Current test UI shows all 60 questions in a flat list with a single 90-minute timer. Two issues:
1. `competency_reference` badge on each question hints at which material it targets (ethics vs. boundaries vs. core competency), which real exams don't reveal.
2. No section structure — real ICF ACC exam uses two timed sections with a break.

## Changes

### 1. Hide competency reference from test-taker

**Files:** `serve.py`, `templates/serve/test.html`

- Remove `competency_reference` from the `safe` dict in `serve.py` `/test/<filename>` route (line 238).
- Remove the `<span class="badge badge-accent q-competency">` element from `test.html` (line 239).
- Keep `competency_reference` in grading data (results page still shows it).

### 2. Two-section exam with per-section timing

**Files:** `templates/serve/test.html`, `templates/serve/results.html`

#### Stage flow

```
[Section 1: Q1-Q30, 39:00 timer]
        ↓ auto or manual
[Break screen: 10:00 timer, "Continue" button]
        ↓ auto or manual
[Section 2: Q31-Q60, 39:00 timer]
        ↓ auto or manual
[POST all answers → results]
```

#### Timing rules

| Event | Behavior |
|---|---|
| All 30 answered before 39min | "Next Section" button appears |
| 39min expires with unanswered | Auto-progress; unanswered marked wrong |
| Break timer expires | Auto-advance to section 2 |
| "Continue" during break | Available immediately (user can skip wait) |
| "Leave Early" during either section | Submits entire exam immediately |

#### UI per stage

**Section 1 / Section 2:**
- Sticky bar: `ICF ACC` · `Section X · Y/30 answered` · `39:00 timer` · `Leave Early` button
- Progress bar fills per-section (resets at break)
- Only the current section's questions are visible
- Questions animate in on section entry
- Bottom buttons: "Leave Early" + "Submit Section" (becomes "Next Section →" once all 30 answered)
- `beforeunload` warning if user tries to close/refresh during exam

**Break screen:**
- Centered card: "Section 1 Complete" header
- Subtext: "Your answers have been saved."
- 10:00 countdown timer
- "Continue to Section 2 →" button (always clickable, timer is advisory)
- No "Leave Early" button (nothing to submit yet)

**Results page:**
- Add section breakdown: Section 1 score + Section 2 score alongside total
- Per-question breakdown unchanged

#### Data handling

- Server sends all 60 questions in one response (no server-side state change)
- Client JS splits questions into two halves (indices 0-29 and 30-59)
- All answers stored in DOM radio inputs; form POSTs all at once
- Grading on server is unchanged — it already grades all questions generically

#### Refresh tolerance

- Radio state persists in DOM across refresh (browser native)
- Stage resets to section 1 on refresh (acceptable for mock exam)
- No sessionStorage/session tracking needed

## Out of scope

- Server-side session state
- Question randomization within sections
- Per-question timer
- Navigation between individual questions
- Partial grading or early section submission to server
