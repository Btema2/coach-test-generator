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
    monkeypatch.setenv("BATCH_SIZE", "7")
    api_key, model, batch_size = _load_env()
    assert api_key == "test-key"
    assert model == "gemini-2.5-pro"
    assert batch_size == 7
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
