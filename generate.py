import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from db import get_existing_scenarios, init_db, insert_questions
from gemini_client import generate_questions

_log = logging.getLogger(__name__)


def _load_batch_size_value() -> int:
    raw_batch = os.getenv("BATCH_SIZE", "").strip()
    if not raw_batch:
        raise SystemExit("Missing required env var: BATCH_SIZE")
    try:
        batch_size = int(raw_batch)
    except ValueError:
        raise SystemExit(f"BATCH_SIZE must be an integer, got: {raw_batch!r}")
    if batch_size < 1:
        raise SystemExit(f"BATCH_SIZE must be >= 1, got: {batch_size}")
    if batch_size % 10 != 0:
        raise SystemExit(f"BATCH_SIZE must be a multiple of 10, got: {batch_size}")
    return batch_size


def _load_batch_size() -> int:
    load_dotenv()
    return _load_batch_size_value()


def _load_env() -> tuple[str, str, int]:
    load_dotenv()
    missing = [v for v in ("GEMINI_API_KEY", "GEMINI_MODEL") if not os.getenv(v, "").strip()]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")
    api_key, model = os.environ["GEMINI_API_KEY"], os.environ["GEMINI_MODEL"]
    batch_size = _load_batch_size_value()
    return api_key, model, batch_size


def _fill_prompt(template: str, batch_size: int, existing: list[str], start_id: int | None = None) -> str:
    db_text = (
        "\n".join(f"{i + 1}. {s}" for i, s in enumerate(existing))
        if existing
        else "No questions generated yet."
    )
    if start_id is None:
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
    for i in range(n_calls):
        start_id = i * 10 + 1
        _log.info("Batch %d/%d (questions %d–%d)", i + 1, n_calls, start_id, start_id + 9)
        filled_prompt = _fill_prompt(template, 10, existing, start_id)
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


def _run_api(batch_size: int, template: str) -> None:
    api_key, model, _ = _load_env()
    with sqlite3.connect("icf_mock_exams.db") as conn:
        init_db(conn)
        existing = get_existing_scenarios(conn)
        all_questions = _run_batched(template, api_key, model, batch_size, existing)
        data = {"mock_exam_batch": all_questions}
        inserted = insert_questions(conn, all_questions)
    json_path = _save_json(data)
    _log.info("Generated %d questions → %s + DB", inserted, json_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Generate ICF ACC mock exam questions.")
    parser.add_argument("--diy", action="store_true", help="Human-in-the-loop mode (no API).")
    parser.add_argument("--port", type=int, default=5000, help="DIY server port.")
    args = parser.parse_args()

    prompt_path = Path("ACC-test-prompt.md")
    if not prompt_path.exists():
        raise SystemExit(f"Prompt template not found: {prompt_path.resolve()}")
    template = prompt_path.read_text()

    if args.diy:
        import diy
        diy.run(template, _load_batch_size(), port=args.port)
        return

    _run_api(_load_batch_size(), template)


if __name__ == "__main__":
    main()
