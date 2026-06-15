# Sectioned Exam — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-06-15-sectioned-exam-design.md`

## Task 1: Hide competency reference from test-taker

**File: `serve.py`**
- In `/test/<filename>` route, remove `competency_reference` from the `safe` dict (currently line ~238-240)
- Keep all other fields in `safe` as-is

**File: `templates/serve/test.html`**
- Remove `<span class="badge badge-accent q-competency">{{ q.competency_reference }}</span>` (line 239)
- Remove `.q-competency` CSS rule (line 116-118)

**Verify:** Start serve.py, open a test — no competency badge visible on questions.

---

## Task 2: Restructure test.html for sectioned exam

Replace the single-page flat list with a multi-stage UI. All changes in `templates/serve/test.html`.

### HTML structure

```
<div id="stage-section1" class="stage active">
  <div class="questions-list">
    {% for q in questions[:30] %}
    ...question card...
    {% endfor %}
  </div>
  <div class="form-footer">
    <button>Leave Early</button>
    <button id="btn-next1">Submit Section</button>
  </div>
</div>

<div id="stage-break" class="stage">
  <div class="break-card">
    <h2>Section 1 Complete</h2>
    <p>Your answers have been saved.</p>
    <div class="timer" id="break-timer">10:00</div>
    <button id="btn-continue">Continue to Section 2 →</button>
  </div>
</div>

<div id="stage-section2" class="stage">
  <div class="questions-list">
    {% for q in questions[30:] %}
    ...question card...
    {% endfor %}
  </div>
  <div class="form-footer">
    <button>Leave Early</button>
    <button id="btn-submit-final">Submit Test</button>
  </div>
</div>
```

All three stages exist in the DOM. Only one has `class="active"` (display:block), others `display:none`.

### Exam bar updates

- Progress text: `Section 1 · 0 / 30 answered` (or Section 2)
- Timer: shows current section countdown (39:00)
- "Leave Early" button: always visible during sections, hidden during break

### CSS changes

- `.stage { display: none; }` / `.stage.active { display: block; }`
- Break screen centered card styles
- Button text changes via JS (`textContent`)

### JavaScript restructure

**State:**
```js
let stage = 'section1';   // 'section1' | 'break' | 'section2'
let sectionRemaining = 39 * 60;
let breakRemaining = 10 * 60;
```

**Functions:**
- `showStage(name)` — hides all stages, shows target, resets progress bar, updates exam bar text
- `tickSection()` — decrements sectionRemaining, auto-submits section on 0
- `tickBreak()` — decrements breakRemaining, auto-advances on 0
- `countSectionAnswered(sectionIndex)` — counts answered radios in current section only
- `updateProgress()` — updates bar for current section (Y/30)
- `submitExam()` — unchanged, posts entire form
- `beforeunload` handler — warns if exam in progress

**Section completion logic:**
- When all 30 in current section answered, change "Submit Section" → "Next Section →"
- Clicking "Next Section" from section 1: calls `showStage('break')`, starts break timer
- Clicking "Submit Test" from section 2: calls `submitExam()`

**Timer transitions:**
- Section timer hits 0 → auto-advance (section1→break, section2→submit)
- Break timer hits 0 → auto-advance to section2

---

## Task 3: Add section breakdown to results

**File: `templates/serve/results.html`**

After the score stats section, add:
```html
<div class="score-sections">
  <div class="section-score">
    <span class="section-label">Section 1</span>
    <span class="section-val">{{ section1_score }}/30</span>
  </div>
  <div class="section-score">
    <span class="section-label">Section 2</span>
    <span class="section-val">{{ section2_score }}/30</span>
  </div>
</div>
```

**File: `serve.py`** — In `/submit/<filename>` route, compute section scores:
```python
section1_graded = graded[:30]
section2_graded = graded[30:]
section1_score = sum(1 for r in section1_graded if r["ok"])
section2_score = sum(1 for r in section2_graded if r["ok"])
```

Pass these to the results template.

**CSS:** Simple flex row with two stat boxes, styled to match existing score-stats.

---

## Task 4: Cleanup and verify

- Remove any dead CSS from old single-section layout
- Test full flow: picker → section 1 → break → section 2 → results
- Test early completion (all answered → Next Section)
- Test force-advance (timer expires)
- Test Leave Early from both sections
- Test results show section breakdown
- Verify competency_reference hidden in test, visible in results
