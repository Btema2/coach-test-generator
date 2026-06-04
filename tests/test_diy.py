import json

from diy import _validate_batch


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
