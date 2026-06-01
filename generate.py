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
