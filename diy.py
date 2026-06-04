import json

_REQUIRED_FIELDS = (
    "question_id",
    "competency_reference",
    "scenario_question",
    "options",
    "ai_rationale",
)
_OPTION_IDS = ("A", "B", "C", "D")
_BATCH_LEN = 10  # Each DIY page always processes exactly one 10-question sub-batch.


def _validate_batch(text: str) -> tuple[list[dict] | None, str | None]:
    """Return (batch, None) on success or (None, error_message) on failure."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"Not valid JSON: {exc}"

    batch = data.get("mock_exam_batch") if isinstance(data, dict) else None
    if not isinstance(batch, list):
        return None, "Missing mock_exam_batch array"
    if len(batch) != _BATCH_LEN:
        return None, f"Expected {_BATCH_LEN} questions, got {len(batch)}"

    for i, q in enumerate(batch, start=1):
        if not isinstance(q, dict):
            return None, f"Q#{i} is not an object"
        for field in _REQUIRED_FIELDS:
            if field not in q:
                return None, f"Q#{i} missing field '{field}'"
        rationale = q["ai_rationale"]
        if not isinstance(rationale, dict) or "explanation" not in rationale:
            return None, f"Q#{i} missing field 'ai_rationale.explanation'"
        opts = q["options"]
        if not isinstance(opts, list) or len(opts) != 4:
            return None, f"Q#{i} options malformed (need 4)"
        if not all(isinstance(o, dict) for o in opts):
            return None, f"Q#{i} options malformed (items must be objects)"
        if [o.get("id") for o in opts] != list(_OPTION_IDS):
            return None, f"Q#{i} options malformed (ids must be A,B,C,D)"
        correct = sum(1 for o in opts if o.get("is_correct") is True)
        if correct != 1:
            return None, f"Q#{i} must have exactly 1 correct (got {correct})"

    return batch, None
