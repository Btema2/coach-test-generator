# DIY Mode Design

**Date:** 2026-06-04
**Status:** Approved, pending implementation plan

## Problem

The Gemini API is expensive. We want an offline alternative: let the user paste the
generation prompt into a free AI chatbot, copy the chatbot's JSON response back, and have
the program process it exactly as it would an API response. A `--diy` flag opens a local
Flask webpage that drives this human-in-the-loop flow.

## Goals

- Add `--diy` flag to `generate.py`.
- Preserve existing sequential batching and cross-batch deduplication.
- Validate pasted JSON strictly (the API got this for free via Gemini `response_schema`).
- Persist each accepted batch to the DB immediately (resilient to mid-run browser close).
- Leave the existing API path untouched.

## Non-Goals

- No multi-user, no remote exposure (bind `127.0.0.1` only).
- No auth, no production WSGI server (Flask dev server is fine for local single-user).
- No change to the prompt template or DB schema.

## Architecture

```
generate.py main()
  argparse --diy?
    no  -> existing API flow (_load_env, _run_batched via Gemini)   # untouched
    yes -> diy.run(template, batch_size, port)
```

### Files

- **`generate.py`** — add `argparse`; on `--diy` branch to `diy.run()`. API path unchanged.
  Add `_load_batch_size()` helper (DIY needs only `BATCH_SIZE`, not API key/model).
- **`diy.py`** — new. Flask server + browser-driven batch loop + `_validate_batch`.
- **Reused (drift guard):** `_fill_prompt` and `_save_json` imported from `generate.py`;
  `init_db`, `get_existing_scenarios`, `insert_questions` from `db.py`. Only the batch
  *loop* is reimplemented (browser-driven instead of API-driven).

### Env

- API mode: full `_load_env()` — requires `GEMINI_API_KEY`, `GEMINI_MODEL`, `BATCH_SIZE`.
- DIY mode: `_load_batch_size()` — requires only `BATCH_SIZE` (no API call made).
- `BATCH_SIZE` validation (int, >= 1, multiple of 10) reused in both paths; runs before the
  server starts in DIY.

## Server: event-driven state machine

The browser's POSTs drive progress — there is no background loop. The Flask process holds
in-memory state plus one long-lived SQLite connection (single user, single thread).

```python
state = {
    "batch_size": int,
    "n_calls":    batch_size // 10,   # e.g. 60 -> 6
    "current":    0,                  # number of batches accepted so far
    "existing":   [...scenarios],     # dedup context, grows per accepted batch
    "completed":  [...questions],     # accumulated for final JSON
}
```

Startup:
1. `init_db(conn)`.
2. `existing = get_existing_scenarios(conn)` — seed dedup from prior runs.
3. Auto-open `http://127.0.0.1:<port>` in browser.

### Endpoints

- **`GET /`** — render current batch:
  - header `Batch (current+1)/n_calls`
  - filled prompt via `_fill_prompt(template, 10, existing, current*10 + 1)`
  - "Copy prompt" button
  - paste `<textarea>` + Submit
  - When `current == n_calls`, redirect to `/done`.
- **`POST /submit`** — validate pasted JSON (strict, see below):
  - fail → re-render `GET /` body with red error message, state unchanged
  - pass → `insert_questions(conn, batch)` immediately; extend `existing` with the
    batch's `scenario_question` values; append to `completed`; `current += 1`.
  - if now last batch → `_save_json({"mock_exam_batch": completed})`, redirect `/done`.
- **`GET /done`** — success page (counts, JSON path). Shut the server down.

## Strict validation — `_validate_batch(text) -> (batch | None, error | None)`

First failure returns a human-readable error string:

| Check | Error message |
|-------|---------------|
| valid JSON | `Not valid JSON: <msg>` |
| `mock_exam_batch` is an array | `Missing mock_exam_batch array` |
| length == 10 | `Expected 10 questions, got N` |
| each item has required fields | `Q#k missing field 'x'` |
| required fields: `question_id`, `competency_reference`, `scenario_question`, `options`, `ai_rationale.explanation` | |
| each `options`: 4 items, ids A–D | `Q#k options malformed` |
| exactly one `is_correct == true` per question | `Q#k must have exactly 1 correct` |

On pass returns `(batch_list, None)`. Mirrors the structure Gemini's `response_schema`
enforced.

Note: validation does **not** reject duplicate `question_id`s across runs — the DB layer's
UNIQUE constraint already logs and skips those in `insert_questions`.

## Persistence

- Per accepted batch: `insert_questions(conn, batch)` immediately. Closing the browser after
  batch 3 of 6 leaves 30 questions saved — and those become dedup context on the next run.
- End of run: `_save_json` writes the combined `jsons/<timestamp>.json` of `completed`.
- Partial run (Ctrl-C / closed browser): DB holds completed batches; no JSON file written.
  Acceptable.

## Error handling / edge cases

- Port busy → try the next port, or honor a `--port` override.
- `BATCH_SIZE` not a positive multiple of 10 → reuse existing validation, exit before server start.
- Bad paste → inline red error, stay on the same batch, no state mutation.
- `Ctrl-C` → incremental saves already persisted; partial run leaves DB populated, no JSON.
- Bind `127.0.0.1` only (never `0.0.0.0`) — local, no network exposure.

## Testing (pytest + Flask test client)

- `_validate_batch`: valid batch; bad JSON; wrong count; missing field; zero correct; two
  correct; malformed options.
- `_load_batch_size`: missing; non-int; not multiple of 10.
- Flask client: `GET /` shows Batch 1/N; `POST /submit` good → advances + inserts (mock DB);
  bad → error rendered + no advance; last batch → JSON written.
- argparse: `--diy` routes to `diy.run` (mocked); absent → API path.

## Open questions

None.
