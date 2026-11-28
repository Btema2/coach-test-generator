# Coach Test Generator

Mock exams for the ICF **ACC** (Associate Certified Coach) credential, in two parts:

- **Question generator** (`generate.py`): writes scenario-based multiple-choice questions on the
  ICF Core Competencies (2025) and the ICF Code of Ethics (2025), using the Gemini API or, at no cost, any
  free AI chatbot.
- **Exam site** (`serve.py`): a bilingual (English / Ukrainian) Flask site where people take the
  exams. It has a timed exam in two sections, a practice mode, accounts, and a history of results.

Not affiliated with or endorsed by the International Coaching Federation.

## Setup

Requires Python 3.13.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in what you need
```

## Run the exam site

```bash
python serve.py                         # http://localhost:5001, opens a browser tab
python serve.py --port 8000 --no-browser
```

Accounts and results go to a local SQLite file (`data/app.db`) unless `DATABASE_URL` is set.
Flask caches templates when debug mode is off, so restart the server after editing them.

## Generate questions

```bash
python generate.py          # Gemini API: needs GEMINI_API_KEY, GEMINI_MODEL, BATCH_SIZE
python generate.py --diy    # no API: a local page walks you through using a free chatbot
```

- `BATCH_SIZE` is the number of questions per run and must be a multiple of 10. Questions are
  requested 10 at a time.
- Each batch's scenarios are added to the next prompt, and scenarios from earlier runs are read
  from `icf_mock_exams.db`, so the model avoids repeating them.
- In DIY mode you copy the prompt into a chatbot and paste its JSON reply back. The reply is
  checked strictly, and each accepted batch is saved to the database straight away.
- The run's questions are written to `jsons/<timestamp>.json`.

The prompt template is [`ACC-test-prompt.md`](ACC-test-prompt.md). It requires each batch to be
about 30% ethics, 30% boundaries (coaching vs. therapy vs. consulting) and 40% Core Competencies.

## Publish an exam set

The site lists every `jsons/*.json` file, and the tests check every one of them. To publish a set:

1. Make sure it has exactly **60 questions**. The exam is two sections of 30, and the tests check this.
2. Add a `meta` block (see the format below).
3. Name it `set-<n>-<lang>.json` and commit it with `git add -f`, because generator output in
   `jsons/` is ignored by default.
4. For a translation, keep the same question order and answer key, and add the pair to
   `test_translations_match_their_source_answer_keys` in `tests/test_serve.py`.

Set 1 (English) keeps its original name, `2026-06-15T19-30-29.json`. Saved results point to an
exam by its file name, so renaming it would break links to past results.

## Exam file format

```json
{
  "meta": {
    "title": "ACC Mock Exam — Set 2",
    "description": "60 new scenarios: ...",
    "language": "en",
    "order": 2
  },
  "mock_exam_batch": [
    {
      "question_id": "1",
      "competency_reference": "Core Competency 7: Evokes Awareness",
      "scenario_question": "A 1-2 sentence scenario, then the question.",
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

Each question needs options `A`–`D` with exactly one correct answer, and no "All of the above" or
"None of the above" options. `meta` is optional, but without it a set gets its file name as its
title and English as its language. Sets are sorted by `order`.

The site groups scores by the number after `Core Competency` (or `Ключова компетенція`) in
`competency_reference`. References that mention ethics are scored together as Ethics.

## Configuration

All settings are environment variables. See [`.env.example`](.env.example).

| Variable | Used by | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | generator (API mode) | Gemini credentials and model |
| `BATCH_SIZE` | generator | Questions per run (a multiple of 10) |
| `BRAND_NAME` | site | Name in page titles |
| `DATABASE_URL` | site | Postgres URL. Empty means SQLite at `data/app.db` |
| `SECRET_KEY` | site | Signs session cookies. Empty means one is generated and kept in the database |
| `ADMIN_PASSWORD` | site | Turns on the answer key at `/admin`, which nothing on the site links to |
| `CONTACT_EMAIL` | site | Shown on the privacy page |
| `PUBLIC_URL` | site | Public https address. Turns on secure cookies |

Accounts are a username and a password (Werkzeug scrypt hashes). No email is collected, so there is
no password reset. An account is optional: guests can take every exam. When a guest signs in or
registers, their results move to the account.

## Deployment

Production runs on Render with `gunicorn serve:app` and a Neon Postgres database:

- Set `DATABASE_URL` to Neon's pooled URL, plus `SECRET_KEY` and optionally `ADMIN_PASSWORD`.
  Render sets `RENDER_EXTERNAL_URL` itself, which does the same job as `PUBLIC_URL`.
- While an exam is open, the page calls `/ping` every 50 seconds so Render's free instance doesn't
  go to sleep in the middle of an exam.
- The Neon project is linked through `.neon` and `neon.ts`. `npm install` gets the Neon config
  packages (`package.json`), and `neon env pull` writes `DATABASE_URL` to `.env.local`.
  `serve.py` loads `.env.local` before `.env`, so **a local run then uses the production
  database**. Delete or rename `.env.local` to go back to SQLite.

## Tests

```bash
python -m pytest
```

The tests clear `DATABASE_URL`, so they never touch a real database. Besides the code, they check
the exam files and that `i18n.py` has the same keys and placeholders in English and Ukrainian.

## Project layout

```
ACC-test-prompt.md       prompt template for the generator
generate.py              generator CLI (Gemini API, or --diy)
gemini_client.py         Gemini call with a JSON response schema and retries on 503
diy.py                   DIY mode: a local page for copying and pasting with a chatbot
db.py                    generator's SQLite store of past questions, used to avoid repeats
serve.py                 exam site (Flask)
store.py                 site storage: users, attempts, settings (SQLAlchemy Core)
i18n.py                  every interface string, in English and Ukrainian
templates/serve/         site pages
static/                  CSS, page scripts, self-hosted fonts, favicon
jsons/                   exam sets (committed) and generator output (ignored)
tests/                   pytest suite
docs/superpowers/        design specs and implementation plans for earlier features
neon.ts, package.json    Neon project config
```

## License

[GNU AGPL v3](LICENSE). The Literata and Onest fonts in `static/fonts/` are under the SIL Open Font
License.
