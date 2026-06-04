import json
import sqlite3

from diy import _validate_batch
from db import init_db


def _question(idx: int, correct_count: int = 1) -> dict:
    opts = [
        {"id": "A", "text": "a", "is_correct": False},
        {"id": "B", "text": "b", "is_correct": False},
        {"id": "C", "text": "c", "is_correct": False},
        {"id": "D", "text": "d", "is_correct": False},
    ]
    opts = [
        {**o, "is_correct": True} if j < correct_count else o
        for j, o in enumerate(opts)
    ]
    return {
        "question_id": str(idx),
        "competency_reference": "Core Competency 1",
        "scenario_question": f"Scenario {idx}",
        "options": opts,
        "ai_rationale": {"explanation": "because"},
    }


def _good_payload(count: int = 10) -> str:
    return json.dumps({"mock_exam_batch": [_question(i) for i in range(count)]})


def test_validate_good_batch():
    batch, err = _validate_batch(_good_payload())
    assert err is None
    assert len(batch) == 10


def test_validate_bad_json():
    batch, err = _validate_batch("{not json")
    assert batch is None
    assert "Not valid JSON" in err


def test_validate_missing_array():
    batch, err = _validate_batch(json.dumps({"foo": []}))
    assert batch is None
    assert "Missing mock_exam_batch array" in err


def test_validate_wrong_count():
    batch, err = _validate_batch(_good_payload(count=9))
    assert batch is None
    assert "Expected 10 questions, got 9" in err


def test_validate_missing_field():
    payload = json.loads(_good_payload())
    del payload["mock_exam_batch"][2]["competency_reference"]
    batch, err = _validate_batch(json.dumps(payload))
    assert batch is None
    assert "competency_reference" in err


def test_validate_zero_correct():
    payload = json.loads(_good_payload())
    payload["mock_exam_batch"][4] = _question(4, correct_count=0)
    batch, err = _validate_batch(json.dumps(payload))
    assert batch is None
    assert "exactly 1 correct" in err


def test_validate_two_correct():
    payload = json.loads(_good_payload())
    payload["mock_exam_batch"][4] = _question(4, correct_count=2)
    batch, err = _validate_batch(json.dumps(payload))
    assert batch is None
    assert "exactly 1 correct" in err


def test_validate_bad_options():
    payload = json.loads(_good_payload())
    payload["mock_exam_batch"][1]["options"] = payload["mock_exam_batch"][1]["options"][:3]
    batch, err = _validate_batch(json.dumps(payload))
    assert batch is None
    assert "options malformed" in err


def test_validate_non_dict_option():
    payload = json.loads(_good_payload())
    payload["mock_exam_batch"][0]["options"] = [None, None, None, None]
    batch, err = _validate_batch(json.dumps(payload))
    assert batch is None
    assert "options malformed" in err


def test_validate_bad_option_ids():
    payload = json.loads(_good_payload())
    payload["mock_exam_batch"][0]["options"][0]["id"] = "X"
    batch, err = _validate_batch(json.dumps(payload))
    assert batch is None
    assert "options malformed" in err


def _make_state(batch_size: int = 20) -> dict:
    return {
        "batch_size": batch_size,
        "n_calls": batch_size // 10,
        "current": 0,
        "existing": [],
        "completed": [],
    }


def _client(monkeypatch, tmp_path, state, template="N={{NUMBER_OF_QUESTIONS}} S={{START_ID}}"):
    from diy import create_app

    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    app = create_app(template, conn, state)
    app.config.update(TESTING=True)
    return app.test_client(), conn


def test_get_root_shows_first_batch(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path, _make_state())
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Batch 1/2" in body
    assert "N=10" in body          # _fill_prompt injected batch size 10
    assert "S=1" in body           # start_id for batch 1


def test_submit_good_advances_and_inserts(monkeypatch, tmp_path):
    state = _make_state()
    client, conn = _client(monkeypatch, tmp_path, state)
    resp = client.post("/submit", data={"payload": _good_payload()})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    assert state["current"] == 1
    assert len(state["existing"]) == 10
    count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    assert count == 10


def test_submit_bad_stays_on_batch(monkeypatch, tmp_path):
    state = _make_state()
    client, conn = _client(monkeypatch, tmp_path, state)
    resp = client.post("/submit", data={"payload": "{bad"})
    body = resp.get_data(as_text=True)
    assert state["current"] == 0
    assert "Not valid JSON" in body
    count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    assert count == 0


def test_submit_last_batch_writes_json(monkeypatch, tmp_path):
    state = _make_state(batch_size=10)   # single batch
    client, conn = _client(monkeypatch, tmp_path, state)
    client.post("/submit", data={"payload": _good_payload()})
    assert state["current"] == 1
    written = list((tmp_path / "jsons").glob("*.json"))
    assert len(written) == 1
    saved = json.loads(written[0].read_text())
    assert len(saved["mock_exam_batch"]) == 10


def test_submit_after_completion_is_noop(monkeypatch, tmp_path):
    state = _make_state(batch_size=10)   # single batch
    client, conn = _client(monkeypatch, tmp_path, state)
    client.post("/submit", data={"payload": _good_payload()})   # completes
    first = list((tmp_path / "jsons").glob("*.json"))
    assert len(first) == 1
    # Resubmit after completion (back button) must not corrupt state or write again
    resp = client.post("/submit", data={"payload": _good_payload()})
    assert resp.status_code == 302
    assert len(state["completed"]) == 10          # not 20
    assert len(list((tmp_path / "jsons").glob("*.json"))) == 1   # no second file
