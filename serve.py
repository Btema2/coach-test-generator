import argparse
import json
import threading
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

JSONS_DIR = Path(__file__).parent / "jsons"

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))

_results: dict = {}


@app.template_filter("fmt_filename")
def fmt_filename(filename: str) -> str:
    name = filename.removesuffix(".json")
    try:
        dt = datetime.strptime(name, "%Y-%m-%dT%H-%M-%S")
        return dt.strftime("%b %-d, %Y · %H:%M")
    except ValueError:
        return filename


def _list_jsons() -> list[str]:
    return sorted(
        (f.name for f in JSONS_DIR.glob("*.json") if f.name != ".gitkeep"),
        reverse=True,
    )


def _load_exam(filename: str) -> list[dict]:
    path = JSONS_DIR / filename
    with path.open() as f:
        return json.load(f)["mock_exam_batch"]


@app.route("/ping")
def ping():
    return "", 204


@app.route("/")
def picker():
    return render_template("serve/picker.html", files=_list_jsons(), admin=False)


@app.route("/test/<filename>")
def test(filename: str):
    try:
        questions = _load_exam(filename)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return redirect(url_for("picker"))
    safe = [
        {
            "question_id": q["question_id"],
            "scenario_question": q["scenario_question"],
            "options": [{"id": o["id"], "text": o["text"]} for o in q["options"]],
        }
        for q in questions
    ]
    return render_template("serve/test.html", questions=safe, filename=filename)


@app.route("/submit/<filename>", methods=["POST"])
def submit(filename: str):
    try:
        questions = _load_exam(filename)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return redirect(url_for("picker"))

    submitted = {
        key[2:]: val
        for key, val in request.form.items()
        if key.startswith("q_")
    }

    graded = []
    score = 0
    for q in questions:
        qid = str(q["question_id"])
        correct = next(o["id"] for o in q["options"] if o["is_correct"])
        selected = submitted.get(qid)
        ok = selected == correct
        if ok:
            score += 1
        graded.append(
            {
                "question_id": qid,
                "competency_reference": q["competency_reference"],
                "scenario_question": q["scenario_question"],
                "options": q["options"],
                "selected": selected,
                "correct": correct,
                "ok": ok,
                "unanswered": selected is None,
                "rationale": q["ai_rationale"]["explanation"],
            }
        )

    token = str(uuid.uuid4())
    total = len(questions)
    unanswered = sum(1 for r in graded if r["unanswered"])
    section1_score = sum(1 for r in graded[:30] if r["ok"])
    section2_score = sum(1 for r in graded[30:] if r["ok"])
    _results[token] = {
        "filename": filename,
        "score": score,
        "total": total,
        "wrong": total - score - unanswered,
        "unanswered": unanswered,
        "passed": score / total >= 0.70,
        "pass_score": round(total * 0.70),
        "score_fill": round(score / total * 314.16, 2),
        "score_pct": round(score / total * 100, 1),
        "section1_score": section1_score,
        "section2_score": section2_score,
        "graded": graded,
    }
    return redirect(url_for("results", token=token))


@app.route("/results/<token>")
def results(token: str):
    data = _results.get(token)
    if not data:
        return redirect(url_for("picker"))
    return render_template("serve/results.html", **data)


@app.route("/admin")
def admin_picker():
    return render_template("serve/picker.html", files=_list_jsons(), admin=True)


@app.route("/admin/<filename>")
def admin_view(filename: str):
    try:
        questions = _load_exam(filename)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return redirect(url_for("admin_picker"))
    return render_template("serve/admin.html", questions=questions, filename=filename, admin=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="ICF ACC Mock Exam Server")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://localhost:{args.port}"
    print(f"\n  Local:   {url}")
    print(f"  Network: accessible on port {args.port}\n")

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
