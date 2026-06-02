import json
from unittest.mock import patch

import pytest

from generate import _fill_prompt, _load_env, _run_batched, _save_json


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


def test_fill_prompt_replaces_start_id():
    template = "Start: {{START_ID}}, next: {{START_ID_PLUS_1}}"
    result = _fill_prompt(template, 5, ["Scenario A", "Scenario B"])
    # 2 existing, so next ID starts at 3, and the one after is 4
    assert "Start: 3, next: 4" in result
    assert "{{START_ID}}" not in result
    assert "{{START_ID_PLUS_1}}" not in result


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
    monkeypatch.setenv("BATCH_SIZE", "10")
    api_key, model, batch_size = _load_env()
    assert api_key == "test-key"
    assert model == "gemini-2.5-pro"
    assert batch_size == 10
    assert isinstance(batch_size, int)


def test_load_env_raises_on_invalid_batch_size(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "model")
    monkeypatch.setenv("BATCH_SIZE", "abc")
    with patch("generate.load_dotenv"):
        with pytest.raises(SystemExit, match="integer"):
            _load_env()


def test_load_env_raises_on_zero_batch_size(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "model")
    monkeypatch.setenv("BATCH_SIZE", "0")
    with patch("generate.load_dotenv"):
        with pytest.raises(SystemExit, match=">= 1"):
            _load_env()


def test_load_env_raises_on_non_multiple_of_ten_batch_size(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "model")
    monkeypatch.setenv("BATCH_SIZE", "15")
    with patch("generate.load_dotenv"):
        with pytest.raises(SystemExit, match="multiple of 10"):
            _load_env()


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

    assert "No questions generated yet." in captured_prompts[0]
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
