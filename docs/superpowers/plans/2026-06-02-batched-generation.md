# Batched Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single Gemini API call with N sequential calls of 10 questions each, validating that BATCH_SIZE is a multiple of 10.

**Architecture:** Add divisibility validation to `_load_env()`, extract `_run_batched()` as a testable loop that accumulates results and grows the existing-scenarios list across calls, then wire it into `main()` in place of the current single call.

**Tech Stack:** Python, pytest, `unittest.mock.patch`, existing `generate.py` / `gemini_client.py`

---

### Task 1: Add multiple-of-10 validation to `_load_env()`

**Files:**
- Modify: `tests/test_generate.py`
- Modify: `generate.py:19-26`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_generate.py` (after the existing `test_load_env_raises_on_zero_batch_size` test):

```python
def test_load_env_raises_on_non_multiple_of_ten_batch_size(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "model")
    monkeypatch.setenv("BATCH_SIZE", "15")
    with patch("generate.load_dotenv"):
        with pytest.raises(SystemExit, match="multiple of 10"):
            _load_env()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/btema2/smart-things/code/ntp/test-generator && \
  .venv/bin/pytest tests/test_generate.py::test_load_env_raises_on_non_multiple_of_ten_batch_size -v
```

Expected: `FAILED` — no multiple-of-10 check exists yet.

- [ ] **Step 3: Add the validation to `generate.py`**

In `generate.py`, replace the `_load_env()` body's final validation block (lines 23-26):

```python
    if batch_size < 1:
        raise SystemExit(f"BATCH_SIZE must be >= 1, got: {batch_size}")
    if batch_size % 10 != 0:
        raise SystemExit(f"BATCH_SIZE must be a multiple of 10, got: {batch_size}")
    return os.environ["GEMINI_API_KEY"], os.environ["GEMINI_MODEL"], batch_size
```

- [ ] **Step 4: Run new test — expects PASS; check for collateral failure**

```bash
cd /home/btema2/smart-things/code/ntp/test-generator && \
  .venv/bin/pytest tests/test_generate.py -v
```

Expected: new test PASSES. `test_load_env_returns_typed_values` **FAILS** — it uses `BATCH_SIZE=7` which is no longer valid.

- [ ] **Step 5: Update the broken test to use a valid batch size**

In `tests/test_generate.py`, change `test_load_env_returns_typed_values`:

```python
def test_load_env_returns_typed_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("BATCH_SIZE", "10")
    api_key, model, batch_size = _load_env()
    assert api_key == "test-key"
    assert model == "gemini-2.5-pro"
    assert batch_size == 10
    assert isinstance(batch_size, int)
```

- [ ] **Step 6: Run all tests — all pass**

```bash
cd /home/btema2/smart-things/code/ntp/test-generator && \
  .venv/bin/pytest tests/test_generate.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git -C /home/btema2/smart-things/code/ntp/test-generator add generate.py tests/test_generate.py
git -C /home/btema2/smart-things/code/ntp/test-generator commit -m "feat: validate BATCH_SIZE is multiple of 10"
```

---

### Task 2: Implement `_run_batched()`

**Files:**
- Modify: `tests/test_generate.py` (add new tests + import)
- Modify: `generate.py` (add function)

- [ ] **Step 1: Add test helpers and import to `tests/test_generate.py`**

Add at the top of `tests/test_generate.py`, updating the import line:

```python
from generate import _fill_prompt, _load_env, _run_batched, _save_json
```

Add these helper functions right below the imports (before any test functions):

```python
def _make_question(idx: int) -> dict:
    return {
        "question_id": str(idx),
        "competency_reference": "Core Competency 1",
        "scenario_question": f"Scenario {idx}",
        "options": [
            {"id": "A", "text": "opt A", "is_correct": True},
            {"id": "B", "text": "opt B", "is_correct": False},
            {"id": "C", "text": "opt C", "is_correct": False},
            {"id": "D", "text": "opt D", "is_correct": False},
        ],
        "ai_rationale": {"explanation": "Because A."},
    }


def _make_api_response(start: int, count: int = 10) -> dict:
    return {"mock_exam_batch": [_make_question(start + i) for i in range(count)]}
```

- [ ] **Step 2: Write the failing tests for `_run_batched()`**

Add after the existing tests in `tests/test_generate.py`:

```python
def test_run_batched_single_call_returns_10_questions():
    template = "Count: {{NUMBER_OF_QUESTIONS}} Existing: {{EXISTING_QUESTIONS_DB}} Start: {{START_ID}} Next: {{START_ID_PLUS_1}}"
    with patch("generate.generate_questions", return_value=_make_api_response(1)) as mock_gq:
        result = _run_batched(template, "key", "model", 10, [])
    assert mock_gq.call_count == 1
    assert len(result) == 10


def test_run_batched_multiple_calls_returns_all_questions():
    template = "Count: {{NUMBER_OF_QUESTIONS}} Existing: {{EXISTING_QUESTIONS_DB}} Start: {{START_ID}} Next: {{START_ID_PLUS_1}}"
    responses = [_make_api_response(1), _make_api_response(11), _make_api_response(21)]
    with patch("generate.generate_questions", side_effect=responses) as mock_gq:
        result = _run_batched(template, "key", "model", 30, [])
    assert mock_gq.call_count == 3
    assert len(result) == 30


def test_run_batched_grows_existing_between_calls():
    template = "Existing: {{EXISTING_QUESTIONS_DB}} Count: {{NUMBER_OF_QUESTIONS}} Start: {{START_ID}} Next: {{START_ID_PLUS_1}}"
    captured_prompts: list[str] = []

    def fake_generate(prompt: str, api_key: str, model: str) -> dict:
        captured_prompts.append(prompt)
        call_num = len(captured_prompts)
        return _make_api_response((call_num - 1) * 10 + 1)

    with patch("generate.generate_questions", side_effect=fake_generate):
        _run_batched(template, "key", "model", 20, [])

    # Call 1 prompt: no existing questions yet
    assert "No questions generated yet." in captured_prompts[0]
    # Call 2 prompt: contains scenario_question from call 1 results
    assert "Scenario 1" in captured_prompts[1]
    assert "Scenario 10" in captured_prompts[1]


def test_run_batched_start_ids_sequence_correctly():
    template = "Start: {{START_ID}} Count: {{NUMBER_OF_QUESTIONS}} Existing: {{EXISTING_QUESTIONS_DB}} Next: {{START_ID_PLUS_1}}"
    captured_prompts: list[str] = []

    def fake_generate(prompt: str, api_key: str, model: str) -> dict:
        captured_prompts.append(prompt)
        call_num = len(captured_prompts)
        return _make_api_response((call_num - 1) * 10 + 1)

    with patch("generate.generate_questions", side_effect=fake_generate):
        _run_batched(template, "key", "model", 30, [])

    assert "Start: 1 " in captured_prompts[0]
    assert "Start: 11 " in captured_prompts[1]
    assert "Start: 21 " in captured_prompts[2]


def test_run_batched_does_not_mutate_initial_existing():
    template = "Count: {{NUMBER_OF_QUESTIONS}} Existing: {{EXISTING_QUESTIONS_DB}} Start: {{START_ID}} Next: {{START_ID_PLUS_1}}"
    initial = ["Pre-existing scenario"]
    with patch("generate.generate_questions", return_value=_make_api_response(2)):
        _run_batched(template, "key", "model", 10, initial)
    assert initial == ["Pre-existing scenario"]


def test_run_batched_with_non_empty_initial_existing():
    template = "Count: {{NUMBER_OF_QUESTIONS}} Existing: {{EXISTING_QUESTIONS_DB}} Start: {{START_ID}} Next: {{START_ID_PLUS_1}}"
    captured_prompts: list[str] = []

    def fake_generate(prompt: str, api_key: str, model: str) -> dict:
        captured_prompts.append(prompt)
        return _make_api_response(len(captured_prompts) * 10 + 1)

    with patch("generate.generate_questions", side_effect=fake_generate):
        _run_batched(template, "key", "model", 10, ["DB scenario 1", "DB scenario 2"])

    assert "1. DB scenario 1" in captured_prompts[0]
    assert "2. DB scenario 2" in captured_prompts[0]
    assert "Start: 3 " in captured_prompts[0]
```

- [ ] **Step 3: Run tests to verify they all fail**

```bash
cd /home/btema2/smart-things/code/ntp/test-generator && \
  .venv/bin/pytest tests/test_generate.py -k "run_batched" -v
```

Expected: all 6 new tests FAIL with `ImportError` or `AttributeError: module 'generate' has no attribute '_run_batched'`.

- [ ] **Step 4: Implement `_run_batched()` in `generate.py`**

Add this function after `_fill_prompt()` (around line 41), before `_save_json()`:

```python
def _run_batched(
    template: str,
    api_key: str,
    model: str,
    batch_size: int,
    initial_existing: list[str],
) -> list[dict]:
    n_calls = batch_size // 10
    existing = list(initial_existing)
    all_questions: list[dict] = []
    log = logging.getLogger(__name__)
    for i in range(n_calls):
        log.info("Batch %d/%d (questions %d–%d)", i + 1, n_calls, len(existing) + 1, len(existing) + 10)
        filled_prompt = _fill_prompt(template, 10, existing)
        data = generate_questions(filled_prompt, api_key, model)
        batch = data["mock_exam_batch"]
        all_questions.extend(batch)
        existing.extend(q["scenario_question"] for q in batch)
    return all_questions
```

- [ ] **Step 5: Run `_run_batched` tests — all pass**

```bash
cd /home/btema2/smart-things/code/ntp/test-generator && \
  .venv/bin/pytest tests/test_generate.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git -C /home/btema2/smart-things/code/ntp/test-generator add generate.py tests/test_generate.py
git -C /home/btema2/smart-things/code/ntp/test-generator commit -m "feat: add _run_batched() for sequential 10-question Gemini calls"
```

---

### Task 3: Wire `_run_batched()` into `main()`

**Files:**
- Modify: `generate.py:53-74` (`main()` function)

- [ ] **Step 1: Update `main()` in `generate.py`**

Replace the current `main()` body from `filled_prompt = ...` through `inserted = ...`:

Current code (lines 65-70):
```python
        existing = get_existing_scenarios(conn)
        filled_prompt = _fill_prompt(template, batch_size, existing)
        data = generate_questions(filled_prompt, api_key, model)
        inserted = insert_questions(conn, data["mock_exam_batch"])
```

Replace with:
```python
        existing = get_existing_scenarios(conn)
        all_questions = _run_batched(template, api_key, model, batch_size, existing)
        data = {"mock_exam_batch": all_questions}
        inserted = insert_questions(conn, data["mock_exam_batch"])
```

The complete updated `main()` should look like:

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    api_key, model, batch_size = _load_env()

    prompt_path = Path("ACC-test-prompt.md")
    if not prompt_path.exists():
        raise SystemExit(f"Prompt template not found: {prompt_path.resolve()}")
    template = prompt_path.read_text()

    with sqlite3.connect("icf_mock_exams.db") as conn:
        init_db(conn)
        existing = get_existing_scenarios(conn)
        all_questions = _run_batched(template, api_key, model, batch_size, existing)
        data = {"mock_exam_batch": all_questions}
        inserted = insert_questions(conn, data["mock_exam_batch"])

    json_path = _save_json(data)
    logging.getLogger(__name__).info("Generated %d questions → %s + DB", inserted, json_path)
```

- [ ] **Step 2: Run the full test suite**

```bash
cd /home/btema2/smart-things/code/ntp/test-generator && \
  .venv/bin/pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git -C /home/btema2/smart-things/code/ntp/test-generator add generate.py
git -C /home/btema2/smart-things/code/ntp/test-generator commit -m "feat: wire _run_batched into main(), replace single Gemini call"
```
