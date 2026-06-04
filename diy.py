import json
import sqlite3

from flask import Flask, redirect, render_template_string, request, url_for

from db import insert_questions
from generate import _fill_prompt, _save_json

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


_PAGE = """
<!doctype html>
<title>DIY Question Generator</title>
<h1>Batch {{ n }}/{{ total }}</h1>
{% if error %}<p style="color:red"><b>{{ error }}</b></p>{% endif %}
<p>1. Copy this prompt into your AI chatbot:</p>
<button onclick="navigator.clipboard.writeText(document.getElementById('p').value)">Copy prompt</button>
<textarea id="p" rows="12" cols="100" readonly>{{ prompt }}</textarea>
<p>2. Paste the chatbot's JSON response here:</p>
<form method="post" action="{{ url_for('submit') }}">
  <textarea name="payload" rows="12" cols="100"></textarea><br>
  <button type="submit">Submit batch</button>
</form>
"""

_DONE = """
<!doctype html>
<title>Done</title>
<h1>Done — {{ count }} questions generated</h1>
<p>Saved to DB and {{ path }}. You can close this tab.</p>
"""


def _render_current(template: str, state: dict, error: str | None = None) -> str:
    n = state["current"]
    start_id = n * 10 + 1
    prompt = _fill_prompt(template, 10, state["existing"], start_id)
    return render_template_string(
        _PAGE, n=n + 1, total=state["n_calls"], prompt=prompt, error=error
    )


def create_app(template: str, conn: sqlite3.Connection, state: dict) -> Flask:
    app = Flask(__name__)
    app.config["_json_path"] = None

    @app.route("/")
    def index():
        if state["current"] >= state["n_calls"]:
            return redirect(url_for("done"))
        return _render_current(template, state)

    @app.route("/submit", methods=["POST"])
    def submit():
        if state["current"] >= state["n_calls"]:
            return redirect(url_for("done"))
        batch, error = _validate_batch(request.form.get("payload", ""))
        if error:
            return _render_current(template, state, error=error)
        insert_questions(conn, batch)
        state["existing"].extend(q["scenario_question"] for q in batch)
        state["completed"].extend(batch)
        state["current"] += 1
        if state["current"] >= state["n_calls"]:
            path = _save_json({"mock_exam_batch": state["completed"]})
            app.config["_json_path"] = path
            return redirect(url_for("done"))
        return redirect(url_for("index"))

    @app.route("/done")
    def done():
        if app.config["_json_path"] is None:
            return redirect(url_for("index"))
        return render_template_string(
            _DONE,
            count=len(state["completed"]),
            path=app.config["_json_path"],
        )

    return app
