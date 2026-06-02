# Batched Generation Design

**Date:** 2026-06-02
**Scope:** `generate.py` — replace single Gemini call with sequential 10-question batches

## Problem

Asking Gemini for large question counts in one call causes hallucination and quality degradation. Sequential smaller calls produce better output.

## Requirements

- `BATCH_SIZE` must be a multiple of 10; any other value raises `SystemExit` at startup
- N questions → N/10 sequential Gemini calls, each requesting exactly 10 questions
- Each call's questions are injected into `{{EXISTING_QUESTIONS_DB}}` for subsequent calls (intra-run deduplication)
- All questions from all calls are combined into one JSON file
- Sequential IDs remain correct across calls (already handled by `_fill_prompt` via `len(existing) + 1`)

## Architecture

Only `generate.py` changes. `gemini_client.py` and `db.py` are untouched.

### Validation change — `_load_env()`

Add after existing `batch_size >= 1` check:

```python
if batch_size % 10 != 0:
    raise SystemExit(f"BATCH_SIZE must be a multiple of 10, got: {batch_size}")
```

### New function — `_run_batched()`

```python
def _run_batched(
    template: str,
    api_key: str,
    model: str,
    batch_size: int,
    initial_existing: list[str],
) -> list[dict]:
```

- Copies `initial_existing` (immutable pattern — no mutation of caller's list)
- Loops `batch_size // 10` times
- Each iteration:
  1. `_fill_prompt(template, 10, existing)` — always requests exactly 10
  2. `generate_questions(filled_prompt, api_key, model)`
  3. Extends `existing` with `scenario_question` from each returned question
  4. Accumulates question dicts
- Returns combined `list[dict]` of all questions

### `main()` wiring

Replace single call:
```python
# before
data = generate_questions(filled_prompt, api_key, model)
inserted = insert_questions(conn, data["mock_exam_batch"])
```

With:
```python
# after
all_questions = _run_batched(template, api_key, model, batch_size, existing)
data = {"mock_exam_batch": all_questions}
inserted = insert_questions(conn, data["mock_exam_batch"])
```

`_save_json(data)` is unchanged — one combined file.

## Data Flow

```
DB existing (list[str])
       │
       ▼
_run_batched() loop (N/10 iterations)
  ├── iter 1: existing[0..k]   → fill prompt → Gemini → 10 questions → existing[k+10]
  ├── iter 2: existing[0..k+10] → fill prompt → Gemini → 10 questions → existing[k+20]
  └── iter N: ...
       │
       ▼
all_questions (list[dict], len = batch_size)
       │
  ┌────┴────┐
  DB insert  JSON file
```

## Testing

New unit tests for `_run_batched()`:
- Mock `generate_questions` to return a fixed 10-question batch per call
- Assert call count equals `batch_size // 10`
- Assert returned list length equals `batch_size`
- Assert `existing` passed to each call grows by 10 per iteration (via prompt capture)
- Assert start IDs sequence correctly across calls

Existing tests for `_load_env()` validation: add cases for `BATCH_SIZE=15` (not multiple of 10) → expects `SystemExit`.

## Out of Scope

- Parallel batch calls (sequential only — preserves ID ordering and deduplication)
- Partial-batch support (non-multiples of 10 are rejected)
- Per-batch JSON files (single combined output only)
