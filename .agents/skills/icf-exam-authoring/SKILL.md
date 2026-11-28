---
name: icf-exam-authoring
description: >-
  Author, audit, validate, and translate ICF ACC mock exam sets in this repository under the 2025 ICF Core Competencies and 2025 ICF Code of Ethics. Use whenever creating new exam sets, rewriting or hardening tricky multiple-choice questions, tightening scenario stems, auditing distractors for leaks or length tells, translating exams between English and Ukrainian, or publishing files to jsons/ for serve.py. Trigger even if the user only asks to write coaching test questions, fix easy questions, or review exam JSONs.
---

# ICF ACC Exam Authoring

Workflow for authoring, auditing, translating, and validating 60-question ICF ACC mock exams for this repository.

## Why This Workflow Exists

Single-pass question generation fails ICF ACC quality in predictable ways: stems explain the rule upfront (for example, stating "the coach and client did not agree to share"), distractors read like obvious caricatures instead of tempting traps, correct options betray themselves through extra clauses or words like "clarify" and "immediately", and broken `competency_reference` formatting or mismatched EN/UK keys break `serve.py` scoring and `tests/test_serve.py`. Separating drafting, blind psychometric auditing, Ukrainian localization, and automated validation solves each failure mode without duplicating `ACC-test-prompt.md`.

## Single Source of Truth

Do not copy ICF rules or JSON schemas inline when editing or generating questions—read these repository files first:

- `ACC-test-prompt.md` — authoritative 2025 ICF Code of Ethics (effective April 1, 2025), 2025 ICF Core Competencies (released September 2025), lean stem guidelines, `1 + 1 + 2` option design, and required JSON schema.
- `references/domain_mapping.md` — 60-question domain blueprint (`18 / 18 / 24`), `15/15/15/15` key balance, `meta` block fields, and canonical EN/UK `competency_reference` strings required by `serve.py`.

## Authoring Workflow

### 1. Plan a Non-Overlapping Blueprint
Before writing questions, read existing sets in `jsons/*.json` (or `icf_mock_exams.db` if present) so scenarios never repeat. For a full 60-question exam:
- Allocate **18 Ethics** (`Code of Ethics Section 1–5`), **18 Boundaries** (`Core Competency 1: Demonstrates Ethical Practice — Coaching vs. ...`), and **24 Core Competencies 2–8**.
- Pre-assign target correct option letters (`A`/`B`/`C`/`D`) to hit **15 / 15 / 15 / 15** across 60 items (or equal counts per slice) without predictable runs.
- Split generation into manageable slices (for example, three 20-question batches) with distinct scenarios and industries per slot.

### 2. Draft Lean Stems and 1 + 1 + 2 Options
Write every item following `ACC-test-prompt.md`:
- Keep stems lean (1–2 sentences plus question prompt, roughly 15–28 words before the question) and withhold resolution clues. State facts neutrally (e.g., "A third party pays for coaching and asks for session topics") so the candidate must infer the ICF boundary.
- Craft options with the **1 + 1 + 2 curve**:
  - **1 strictly ICF-aligned key** (client autonomy, partnering, explicit consent, non-attachment, scope integrity).
  - **1 clearly wrong option** written in calm, plausible exam prose rather than cartoonishly rude language.
  - **2 highly plausible distractors** using coaching verbs (`Explore...`, `Ask...`, `Acknowledge...`, `Clarify...`) that tempt practicing coaches (premature Competency 8 action, disguised leading hypotheses, polite boundary erosion under sponsor pressure, rigid over-referral, or "why" analysis).
- Keep all four options parallel in grammar and length (around 8–16 words each) and include a rationale covering all four options under 2025 ICF standards.

### 3. Run a Blind Psychometric Audit
Have a fresh pass (or dedicated reviewer subagent) audit every item independently before translating or publishing:
- Strip any leftover stem clues, dramatic clinical exaggerations, or keyword echoes between stem and key.
- Verify only **one** option is defensibly right under 2025 ICF standards; sharpen any pair of equally valid open questions so the distractor violates a concrete ICF principle.
- Eliminate surface cues: balance option word-count spreads, avoid stuffing extra commas/`and`-chains into correct answers, and rotate coaching buzzwords (`clarify`, `boundaries`, `explore`) into distractors while stripping giveaway adverbs (`immediately`, `completely`, `never`, `without judgment`).

### 4. Translate to Ukrainian With Exact Parity
When localizing an English set (or creating a bilingual pair):
- Keep `question_id` order, option order (`A`–`D`), `is_correct` booleans, and the first digit of `competency_reference` identical to the English source (`test_translations_match_their_source_answer_keys` enforces this).
- Use the canonical Ukrainian `competency_reference` mappings in `references/domain_mapping.md` so `serve.py`'s `_area()` groups Competencies 1–8 and Ethics identically in both languages.
- Translate `scenario_question`, `options`, and `ai_rationale.explanation` into idiomatic ICF Ukraine coaching prose while keeping Ukrainian option lengths balanced and free of giveaways or banned phrases ("Усе вищезазначене", "Жодне з переліченого").

### 5. Validate and Publish
Before finalizing or committing exam files:
1. Preserve filenames of existing published sets (e.g., `2026-06-15T19-30-29.json`, `set-1-uk.json`, `set-2-en.json`, `set-2-uk.json`) because saved user attempts reference the filename.
2. Add or verify the `meta` block (`title`, `description`, `language`, `order`) for published sets.
3. Run the bundled validator script:
   - Single file (or partial draft with `--allow-partial`):
     `python3 scripts/validate_exam.py <path-to-exam.json> [--allow-partial]`
   - Bilingual pair parity check:
     `python3 scripts/validate_exam.py <en.json> --pair <uk.json> [--allow-partial]`
4. Run the repository test suite (`pytest`) and remember that `jsons/*.json` is gitignored by default, so newly published files require `git add -f`.
