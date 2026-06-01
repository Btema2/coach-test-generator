# Gemini Question Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that generates ICF ACC mock exam questions via the Gemini API, persists them to SQLite, and saves raw JSON responses to a timestamped file.

**Architecture:** Three modules (`db.py`, `gemini_client.py`, `generate.py`) with clear separation — DB logic, API logic, and orchestration are independent. `generate.py` is the entry point that wires them together.

**Tech Stack:** Python 3.11+, `google-genai`, `python-dotenv`, SQLite (`sqlite3` stdlib), `pytest`

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `db.py` | Create | DB init, fetch existing scenarios, insert questions |
| `gemini_client.py` | Create | Response schema, retry wrapper, API call |
| `generate.py` | Create | Orchestration: load env → DB → prompt → API → save |
| `requirements.txt` | Create | `google-genai`, `python-dotenv`, `pytest` |
| `pyproject.toml` | Create | pytest config (`pythonpath = ["."]`) |
| `.env.example` | Create | Template for required env vars |
| `.gitignore` | Create | Exclude `.env`, `*.db`, `jsons/*.json` |
| `jsons/.gitkeep` | Create | Keep `jsons/` folder in git |
| `tests/__init__.py` | Create | Empty, marks test package |
| `tests/test_db.py` | Create | Unit tests for `db.py` |
| `tests/test_gemini_client.py` | Create | Unit tests for `gemini_client.py` |
| `tests/test_generate.py` | Create | Unit tests for `generate.py` helpers |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `jsons/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
google-genai
python-dotenv
pytest
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 3: Create `.env.example`**

```
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-2.5-pro
BATCH_SIZE=10
```

- [ ] **Step 4: Create `.gitignore`**

```
.env
icf_mock_exams.db
jsons/*.json
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 5: Create `jsons/.gitkeep` and `tests/__init__.py`**

```bash
mkdir -p jsons tests
touch jsons/.gitkeep tests/__init__.py
```

- [ ] **Step 6: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 7: Commit scaffolding**

```bash
git add requirements.txt pyproject.toml .env.example .gitignore jsons/.gitkeep tests/__init__.py
git commit -m "chore: add project scaffolding and dependencies"
```

---

## Task 2: `db.py` — Database Layer (TDD)

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db.py`:

```python
import json
import sqlite3

import pytest

from db import get_existing_scenarios, init_db, insert_questions


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_db(c)
    yield c
    c.close()


def test_init_db_creates_table(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='questions'"
    )
    assert cursor.fetchone() is not None


def test_get_existing_scenarios_empty(conn):
    assert get_existing_scenarios(conn) == []


def test_get_existing_scenarios_returns_texts(conn):
    conn.execute(
        "INSERT INTO questions (question_id, competency_reference, scenario_question, options, explanation)"
        " VALUES (?,?,?,?,?)",
        ("ABC12345", "CC7", "A coach notices a shift in tone...", "[]", "Explanation"),
    )
    conn.commit()
    result = get_existing_scenarios(conn)
    assert result == ["A coach notices a shift in tone..."]


def test_insert_questions_returns_count(conn):
    questions = [
        {
            "question_id": "QX4A9B2C",
            "competency_reference": "Core Competency 7: Evokes Awareness",
            "scenario_question": "A coach is working with a client who feels stuck...",
            "options": [
                {"id": "A", "text": "Option A", "is_correct": False},
                {"id": "B", "text": "Option B", "is_correct": True},
                {"id": "C", "text": "Option C", "is_correct": False},
                {"id": "D", "text": "Option D", "is_correct": False},
            ],
            "ai_rationale": {"explanation": "B is correct because it is non-directive."},
        }
    ]
    inserted = insert_questions(conn, questions)
    assert inserted == 1


def test_insert_questions_persists_data(conn):
    questions = [
        {
            "question_id": "QX4A9B2C",
            "competency_reference": "Core Competency 7: Evokes Awareness",
            "scenario_question": "A coach is working with a client who feels stuck...",
            "options": [
                {"id": "A", "text": "Option A", "is_correct": False},
                {"id": "B", "text": "Option B", "is_correct": True},
                {"id": "C", "text": "Option C", "is_correct": False},
                {"id": "D", "text": "Option D", "is_correct": False},
            ],
            "ai_rationale": {"explanation": "B is correct because it is non-directive."},
        }
    ]
    insert_questions(conn, questions)
    cursor = conn.execute("SELECT question_id, options FROM questions")
    row = cursor.fetchone()
    assert row[0] == "QX4A9B2C"
    assert json.loads(row[1])[1]["is_correct"] is True


def test_insert_questions_skips_duplicate(conn):
    questions = [
        {
            "question_id": "DUPLICATE",
            "competency_reference": "CC1",
            "scenario_question": "Scenario A",
            "options": [],
            "ai_rationale": {"explanation": "Exp"},
        }
    ]
    insert_questions(conn, questions)
    inserted = insert_questions(conn, questions)
    assert inserted == 0
    cursor = conn.execute("SELECT COUNT(*) FROM questions WHERE question_id='DUPLICATE'")
    assert cursor.fetchone()[0] == 1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Implement `db.py`**

```python
import json
import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id          TEXT UNIQUE,
            competency_reference TEXT,
            scenario_question    TEXT,
            options              TEXT,
            explanation          TEXT
        )
        """
    )
    conn.commit()


def get_existing_scenarios(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.execute("SELECT scenario_question FROM questions")
    return [row[0] for row in cursor.fetchall()]


def insert_questions(conn: sqlite3.Connection, questions: list[dict]) -> int:
    inserted = 0
    for q in questions:
        try:
            conn.execute(
                """
                INSERT INTO questions
                    (question_id, competency_reference, scenario_question, options, explanation)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    q["question_id"],
                    q["competency_reference"],
                    q["scenario_question"],
                    json.dumps(q["options"]),
                    q["ai_rationale"]["explanation"],
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            print(f"Warning: duplicate question_id '{q['question_id']}', skipping")
    conn.commit()
    return inserted
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add db layer with init, fetch, and insert"
```

---

## Task 3: `gemini_client.py` — API Layer (TDD)

**Files:**
- Create: `gemini_client.py`
- Create: `tests/test_gemini_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_gemini_client.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors

from gemini_client import _call_with_503_retry, generate_questions


def _make_server_error(code: int) -> genai_errors.ServerError:
    err = genai_errors.ServerError.__new__(genai_errors.ServerError)
    err.code = code
    return err


def test_call_with_503_retry_succeeds_first_try():
    fn = MagicMock(return_value="ok")
    result = _call_with_503_retry(fn, "arg1", key="val")
    assert result == "ok"
    fn.assert_called_once_with("arg1", key="val")


def test_call_with_503_retry_retries_once_on_503():
    err = _make_server_error(503)
    fn = MagicMock(side_effect=[err, "ok"])
    with patch("gemini_client.time.sleep") as mock_sleep:
        result = _call_with_503_retry(fn, "arg")
    assert result == "ok"
    mock_sleep.assert_called_once_with(60)


def test_call_with_503_retry_raises_non_503():
    err = _make_server_error(500)
    fn = MagicMock(side_effect=err)
    with pytest.raises(genai_errors.ServerError):
        _call_with_503_retry(fn)


def test_call_with_503_retry_raises_after_all_retries():
    err = _make_server_error(503)
    fn = MagicMock(side_effect=[err, err, err])
    with patch("gemini_client.time.sleep"):
        with pytest.raises(genai_errors.ServerError):
            _call_with_503_retry(fn)


def test_generate_questions_returns_parsed_dict():
    mock_response = MagicMock()
    mock_response.text = '{"mock_exam_batch": []}'

    with patch("gemini_client.genai.Client") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.return_value = mock_response
        with patch("gemini_client._call_with_503_retry") as mock_retry:
            mock_retry.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
            result = generate_questions("prompt text", "fake-api-key", "gemini-2.5-pro")

    assert result == {"mock_exam_batch": []}
    MockClient.assert_called_once_with(api_key="fake-api-key")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_gemini_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'gemini_client'`

- [ ] **Step 3: Implement `gemini_client.py`**

```python
import json
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

_RETRY_DELAYS = (60, 300)

_RESPONSE_SCHEMA = genai.types.Schema(
    type=genai.types.Type.OBJECT,
    required=["mock_exam_batch"],
    properties={
        "mock_exam_batch": genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=[
                    "question_id",
                    "competency_reference",
                    "scenario_question",
                    "options",
                    "ai_rationale",
                ],
                properties={
                    "question_id": genai.types.Schema(type=genai.types.Type.STRING),
                    "competency_reference": genai.types.Schema(type=genai.types.Type.STRING),
                    "scenario_question": genai.types.Schema(type=genai.types.Type.STRING),
                    "options": genai.types.Schema(
                        type=genai.types.Type.ARRAY,
                        items=genai.types.Schema(
                            type=genai.types.Type.OBJECT,
                            required=["id", "text", "is_correct"],
                            properties={
                                "id": genai.types.Schema(type=genai.types.Type.STRING),
                                "text": genai.types.Schema(type=genai.types.Type.STRING),
                                "is_correct": genai.types.Schema(type=genai.types.Type.BOOLEAN),
                            },
                        ),
                    ),
                    "ai_rationale": genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        required=["explanation"],
                        properties={
                            "explanation": genai.types.Schema(type=genai.types.Type.STRING),
                        },
                    ),
                },
            ),
        ),
    },
)


def _call_with_503_retry(fn, *args, **kwargs):
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        try:
            return fn(*args, **kwargs)
        except genai_errors.ServerError as exc:
            if exc.code != 503:
                raise
            print(f"⚠️ Gemini 503 error. Attempt {attempt}. Waiting {delay}s...")
            time.sleep(delay)
    return fn(*args, **kwargs)


def generate_questions(prompt: str, api_key: str, model: str) -> dict:
    client = genai.Client(api_key=api_key)
    response = _call_with_503_retry(
        client.models.generate_content,
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.5,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
        ),
    )
    return json.loads(response.text.strip())
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_gemini_client.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add gemini_client.py tests/test_gemini_client.py
git commit -m "feat: add gemini client with schema, retry wrapper, and API call"
```

---

## Task 4: `generate.py` — Orchestrator (TDD)

**Files:**
- Create: `generate.py`
- Create: `tests/test_generate.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_generate.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from generate import _fill_prompt, _load_env, _save_json


def test_fill_prompt_replaces_batch_size():
    template = "Generate {{NUMBER_OF_QUESTIONS}} questions."
    result = _fill_prompt(template, 5, [])
    assert "5" in result
    assert "{{NUMBER_OF_QUESTIONS}}" not in result


def test_fill_prompt_injects_numbered_scenarios():
    template = "Existing: {{EXISTING_QUESTIONS_DB}}"
    result = _fill_prompt(template, 5, ["Scenario A", "Scenario B"])
    assert "1. Scenario A" in result
    assert "2. Scenario B" in result
    assert "{{EXISTING_QUESTIONS_DB}}" not in result


def test_fill_prompt_no_existing_scenarios():
    template = "Existing: {{EXISTING_QUESTIONS_DB}}"
    result = _fill_prompt(template, 5, [])
    assert "No questions generated yet." in result


def test_save_json_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = {"mock_exam_batch": [{"question_id": "TEST1234"}]}
    path = _save_json(data)
    assert path.exists()
    assert json.loads(path.read_text()) == data


def test_save_json_creates_jsons_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _save_json({"mock_exam_batch": []})
    assert (tmp_path / "jsons").is_dir()


def test_save_json_filename_is_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _save_json({"mock_exam_batch": []})
    assert path.parent.name == "jsons"
    assert path.suffix == ".json"
    assert path.stem[0].isdigit()


def test_load_env_raises_on_missing_vars(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("BATCH_SIZE", raising=False)
    with patch("generate.load_dotenv"):  # prevent .env file from re-populating cleared vars
        with pytest.raises(SystemExit) as exc_info:
            _load_env()
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_load_env_returns_typed_values(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("BATCH_SIZE", "7")
    api_key, model, batch_size = _load_env()
    assert api_key == "test-key"
    assert model == "gemini-2.5-pro"
    assert batch_size == 7
    assert isinstance(batch_size, int)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_generate.py -v
```

Expected: `ModuleNotFoundError: No module named 'generate'`

- [ ] **Step 3: Implement `generate.py`**

```python
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from db import get_existing_scenarios, init_db, insert_questions
from gemini_client import generate_questions


def _load_env() -> tuple[str, str, int]:
    load_dotenv()
    missing = [v for v in ("GEMINI_API_KEY", "GEMINI_MODEL", "BATCH_SIZE") if not os.getenv(v)]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")
    return os.environ["GEMINI_API_KEY"], os.environ["GEMINI_MODEL"], int(os.environ["BATCH_SIZE"])


def _fill_prompt(template: str, batch_size: int, existing: list[str]) -> str:
    db_text = (
        "\n".join(f"{i + 1}. {s}" for i, s in enumerate(existing))
        if existing
        else "No questions generated yet."
    )
    return (
        template.replace("{{NUMBER_OF_QUESTIONS}}", str(batch_size))
        .replace("{{EXISTING_QUESTIONS_DB}}", db_text)
    )


def _save_json(data: dict) -> Path:
    jsons_dir = Path("jsons")
    jsons_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    path = jsons_dir / f"{timestamp}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def main() -> None:
    api_key, model, batch_size = _load_env()
    template = Path("ACC-test-prompt.md").read_text()

    conn = sqlite3.connect("icf_mock_exams.db")
    init_db(conn)

    existing = get_existing_scenarios(conn)
    filled_prompt = _fill_prompt(template, batch_size, existing)

    data = generate_questions(filled_prompt, api_key, model)

    json_path = _save_json(data)
    inserted = insert_questions(conn, data["mock_exam_batch"])
    conn.close()

    print(f"Generated {inserted} questions → {json_path} + DB")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_generate.py -v
```

Expected: 8 passed

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: 19 passed, 0 failed

- [ ] **Step 6: Commit**

```bash
git add generate.py tests/test_generate.py
git commit -m "feat: add generate orchestrator with env loading, prompt filling, and JSON saving"
```

---

## Task 5: Final Wiring and Smoke Check

**Files:**
- No new files

- [ ] **Step 1: Create `.env` from `.env.example`**

```bash
cp .env.example .env
# Edit .env and fill in real GEMINI_API_KEY, GEMINI_MODEL, BATCH_SIZE
```

- [ ] **Step 2: Verify full test suite is green**

```bash
pytest -v --tb=short
```

Expected: 19 passed

- [ ] **Step 3: Dry-run without real API key (confirm env validation)**

```bash
GEMINI_API_KEY="" python generate.py
```

Expected output contains: `Missing required env vars: GEMINI_API_KEY`

- [ ] **Step 4: Run with real credentials (live test)**

```bash
python generate.py
```

Expected:
- `jsons/2026-XX-XXTXX-XX-XX.json` created with `mock_exam_batch` array
- `icf_mock_exams.db` created with rows in `questions` table
- Terminal prints: `Generated N questions → jsons/....json + DB`

Verify DB:
```bash
sqlite3 icf_mock_exams.db "SELECT question_id, competency_reference FROM questions LIMIT 5;"
```

- [ ] **Step 5: Final commit**

```bash
git add .gitignore
git commit -m "chore: finalize project structure"
```
