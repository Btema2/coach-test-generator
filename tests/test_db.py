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
