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
