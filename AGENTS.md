# AGENTS.md

This file provides guidance to AI coding agents working with this repository.
User-facing setup and usage are in `README.md`.

## Project Purpose

Two parts in one repo:
- **Generator** (`generate.py`): CLI that writes ICF ACC (Associate Certified Coach) mock exam
  questions with the Gemini API (or a free chatbot in DIY mode), following the ICF Core Competencies
  (2025) and the ICF Code of Ethics (2025). Output is JSON in `jsons/`.
- **Exam site** (`serve.py`): public bilingual (EN/UK) Flask site where people take those exams.

## Commands

- Tests: `.venv/bin/python -m pytest` (Python 3.13; deps in `requirements.txt`).
- Site: `python serve.py [--port N] [--no-browser]` (default port 5001). Production: `gunicorn serve:app`.
- Generator: `python generate.py` (API) or `python generate.py --diy [--port N]`.

## Generator

- `ACC-test-prompt.md`: the prompt template. Variables filled by `generate._fill_prompt`:
  `{{NUMBER_OF_QUESTIONS}}`, `{{EXISTING_QUESTIONS_DB}}` (scenarios already written, for dedup),
  `{{START_ID}}` and `{{START_ID_PLUS_1}}` (question IDs are sequential numbers as strings, from 1 per run).
- `gemini_client.py`: one Gemini call with a JSON response schema; retries 503s (after 60 s, then 300 s).
- `db.py`: SQLite `icf_mock_exams.db` of past questions. Its scenarios feed the dedup context.
- `BATCH_SIZE` must be a multiple of 10. Runs go 10 questions per call, and each call's scenarios
  are added to the next call's dedup context. Output goes to `jsons/<timestamp>.json`.
- Each batch should be about 30% ethics (Code of Ethics Sections 1–5), 30% boundaries (coaching vs.
  therapy vs. consulting) and 40% Core Competencies.
- Agent skill `.agents/skills/icf-exam-authoring/` (symlinked at `.claude/skills`) packages the
  multi-step authoring, blind psychometric audit, Ukrainian localization, and validation workflow
  (`scripts/validate_exam.py`) on top of `ACC-test-prompt.md`.

### DIY Mode (no API cost)

`python generate.py --diy [--port N]`:
1. A local Flask page opens in the browser.
2. Copy the shown prompt into any free AI chatbot.
3. Paste the chatbot's JSON response back; it is strictly validated (`diy._validate_batch`).
4. Each accepted batch of 10 is saved to the DB immediately and its scenarios
   feed the next batch's dedup context. Final combined JSON lands in `jsons/`.

DIY mode requires only `BATCH_SIZE` (no `GEMINI_API_KEY`/`GEMINI_MODEL`).

## Web App (`serve.py`)

- `i18n.py`: every interface string, EN + UK (same keys and placeholders in both; tests enforce it).
- `store.py`: SQLAlchemy Core: users (username + password hash), exam attempts, app settings.
  `DATABASE_URL` (Postgres in production; local SQLite at `data/app.db` by default). The Neon project is
  linked in `.neon` / `neon.ts`; `neon env pull` writes its `DATABASE_URL` (pooled) to `.env.local`, which
  `serve.py` loads before `.env`, so a local run then uses the Neon `production` branch.
- Accounts are username + password (Werkzeug scrypt hashes). No email is collected or sent, so there
  is no password reset.
- `/` is the exam list (one click to an exam or to sign in); `/exams` 301s there. It should read as a
  self-built practice utility, not a product: home icon instead of a brand, no footer, no marketing
  hero, FAQ or sample question. The "not affiliated with ICF" line lives in the home intro.
- Look: every page uses the frame of the Pearson VUE test driver (blue title bar, light-blue tool
  bar, white page, Arial, square buttons, bordered panels), always light. Colors and their contrast
  are at the top of `app.css`.
- The timed exam (`test.html`, `exam.js`, `.cbt-*` styles) copies the Pearson VUE test driver the real
  ACC exam runs in, and is always light: title bar with Time Remaining (HH:MM:SS) and "N of 30",
  Flag for Review, Previous/Next, then an Item Review Screen (Review All / Incomplete / Flagged).
  End Review closes the section for good, as in ICF's ACC candidate guide.
- `templates/serve/` + `static/`: pages, `app.css`, and per-page scripts (`exam.js` keeps the
  in-progress exam in localStorage with wall-clock deadlines and pings `/ping` to keep Render awake;
  `practice.js` checks answers via `/api/check/...`).
- `/admin` (answer key) is off unless `ADMIN_PASSWORD` is set, and is never linked publicly.
- Accounts are optional: guests can take every exam. A guest's results move to the account when
  they sign in or register.
- Flask caches templates when not in debug mode: restart the server after editing them.
- The exam is two timed sections of 30 questions (39 min each) with a 10-minute break, matching
  the real ACC exam.

See `.env.example` for all settings.

## Exam Sets (`jsons/`)

- The site lists, and `tests/test_serve.py` validates, **every** `jsons/*.json`. Generator output is
  gitignored, so a stray local file can still fail tests or show up on a local site.
- Published sets are force-added (`git add -f`), have exactly 60 questions, and carry a `meta` block.
  Translations keep the source's order and answer key; pairs are listed in
  `test_translations_match_their_source_answer_keys`.
- Attempts store the exam **file name**, so don't rename a published set (this is why Set 1 EN is
  still `2026-06-15T19-30-29.json`).

## JSON Schema

```json
{
  "meta": { "title": "...", "description": "...", "language": "en", "order": 1 },
  "mock_exam_batch": [
    {
      "question_id": "1",
      "competency_reference": "e.g. 'Core Competency 7: Evokes Awareness'",
      "scenario_question": "1-2 sentence scenario + question prompt",
      "options": [
        { "id": "A", "text": "...", "is_correct": false },
        { "id": "B", "text": "...", "is_correct": true },
        { "id": "C", "text": "...", "is_correct": false },
        { "id": "D", "text": "...", "is_correct": false }
      ],
      "ai_rationale": { "explanation": "..." }
    }
  ]
}
```

`meta` is added by hand when publishing (the generator doesn't write it). Exactly one option per
question has `is_correct: true`. No "All/None of the above". Score areas come from the number after
`Core Competency` / `Ключова компетенція` in `competency_reference`; references mentioning ethics
group as Ethics.
