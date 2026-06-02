import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from db import get_existing_scenarios, init_db, insert_questions
from gemini_client import generate_questions


def _load_env() -> tuple[str, str, int]:
    load_dotenv()
    missing = [v for v in ("GEMINI_API_KEY", "GEMINI_MODEL", "BATCH_SIZE") if not os.getenv(v, "").strip()]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")
    raw_batch = os.environ["BATCH_SIZE"]
    try:
        batch_size = int(raw_batch)
    except ValueError:
        raise SystemExit(f"BATCH_SIZE must be an integer, got: {raw_batch!r}")
    if batch_size < 1:
        raise SystemExit(f"BATCH_SIZE must be >= 1, got: {batch_size}")
    if batch_size % 10 != 0:
        raise SystemExit(f"BATCH_SIZE must be a multiple of 10, got: {batch_size}")
    return os.environ["GEMINI_API_KEY"], os.environ["GEMINI_MODEL"], batch_size


def _fill_prompt(template: str, batch_size: int, existing: list[str]) -> str:
    db_text = (
        "\n".join(f"{i + 1}. {s}" for i, s in enumerate(existing))
        if existing
        else "No questions generated yet."
    )
    start_id = len(existing) + 1
    return (
        template.replace("{{NUMBER_OF_QUESTIONS}}", str(batch_size))
        .replace("{{EXISTING_QUESTIONS_DB}}", db_text)
        .replace("{{START_ID}}", str(start_id))
        .replace("{{START_ID_PLUS_1}}", str(start_id + 1))
    )


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


def _save_json(data: dict) -> Path:
    jsons_dir = Path("jsons")
    jsons_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    path = jsons_dir / f"{timestamp}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


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
        filled_prompt = _fill_prompt(template, batch_size, existing)
        data = generate_questions(filled_prompt, api_key, model)
        inserted = insert_questions(conn, data["mock_exam_batch"])

    json_path = _save_json(data)
    logging.getLogger(__name__).info("Generated %d questions → %s + DB", inserted, json_path)


if __name__ == "__main__":
    main()
