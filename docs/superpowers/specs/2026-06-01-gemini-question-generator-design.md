# ICF Mock Exam Question Generator — Design Spec

**Date:** 2026-06-01  
**Status:** Approved

---

## Purpose

Python CLI that generates unique ICF ACC mock exam questions via the Google Gemini API and persists them to SQLite. Prevents duplicates by injecting existing scenario texts into the prompt before each API call.

---

## File Structure

```
test-generator/
├── ACC-test-prompt.md          # prompt template (existing)
├── generate.py                 # orchestrator / entry point
├── db.py                       # DB init, fetch, insert
├── gemini_client.py            # Gemini schema, retry wrapper, API call
├── .env                        # secrets + config (not committed)
├── .env.example                # committed template
├── requirements.txt
├── jsons/                      # raw JSON response per run
│   └── 2026-06-01T17-44-00.json
└── icf_mock_exams.db           # SQLite DB, created on first run
```

---

## Environment Variables (`.env`)

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini API key |
| `GEMINI_MODEL` | Model name (e.g. `gemini-2.5-pro`) |
| `BATCH_SIZE` | Number of questions per run (e.g. `10`) |

Validated at startup — missing vars cause immediate exit with a clear error message.

---

## Database Schema (`icf_mock_exams.db`)

Table: `questions`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | PK, autoincrement |
| `question_id` | TEXT | 8-char alphanumeric from JSON |
| `competency_reference` | TEXT | e.g. "Core Competency 7" |
| `scenario_question` | TEXT | 3–5 sentence scenario |
| `options` | TEXT | JSON string of options array |
| `explanation` | TEXT | from `ai_rationale.explanation` |

---

## Components

### `db.py`

- `init_db(conn)` — `CREATE TABLE IF NOT EXISTS questions ...`
- `get_existing_scenarios(conn) -> list[str]` — `SELECT scenario_question FROM questions`
- `insert_questions(conn, questions: list[dict])` — batch INSERT; skips rows with duplicate `question_id` (logs warning)

### `gemini_client.py`

- `_RESPONSE_SCHEMA` — `genai.types.Schema` for `mock_exam_batch` array:
  - Each item: `question_id`, `competency_reference`, `scenario_question`, `options[]` (`id`, `text`, `is_correct`), `ai_rationale` (`explanation`)
- `_call_with_503_retry(fn, *args, **kwargs)` — retries on `genai_errors.ServerError` code 503 with delays of 60s then 300s; raises on third failure or non-503 errors
- `generate_questions(prompt: str, api_key: str, model: str) -> dict` — creates `genai.Client`, calls `generate_content` with `response_mime_type="application/json"` and `_RESPONSE_SCHEMA`, returns parsed dict

### `generate.py` (orchestrator)

Execution order:
1. Load `.env` → validate `GEMINI_API_KEY`, `GEMINI_MODEL`, `BATCH_SIZE`
2. Open SQLite connection → `init_db(conn)`
3. `get_existing_scenarios(conn)` → format as numbered list string
4. Load `ACC-test-prompt.md` → replace `{{NUMBER_OF_QUESTIONS}}` and `{{EXISTING_QUESTIONS_DB}}`
5. `generate_questions(filled_prompt, api_key, model)` → response dict
6. Save raw JSON to `jsons/<ISO-timestamp>.json` (create `jsons/` if absent)
7. `insert_questions(conn, response["mock_exam_batch"])`
8. Print: `Generated N questions → jsons/<file> + DB`

---

## Data Flow

```
generate.py
  ├─ db.py: get_existing_scenarios() → list[str]
  ├─ fill ACC-test-prompt.md template
  ├─ gemini_client.py: generate_questions() → dict
  ├─ save jsons/<timestamp>.json
  └─ db.py: insert_questions()
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing `.env` var | Exit immediately with named var in error message |
| Gemini 503 | Retry at 60s, 300s; raise on third failure |
| JSON parse failure | Print raw response text; exit with error |
| Duplicate `question_id` | Skip row; print warning; continue |
| `jsons/` dir missing | Create automatically |

---

## Dependencies (`requirements.txt`)

```
google-genai
python-dotenv
```

---

## Prompt Template Variables

| Variable | Injected value |
|---|---|
| `{{NUMBER_OF_QUESTIONS}}` | Value of `BATCH_SIZE` |
| `{{EXISTING_QUESTIONS_DB}}` | Numbered list of existing `scenario_question` texts |

---

## Out of Scope

- Web UI or API server
- Export to CSV or other formats
- Question editing or deletion
- Authentication
