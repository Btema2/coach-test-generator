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

DEFAULT_LANG = "en"
LANG_COOKIE = "lang"

# UI strings per language. Exam content comes from the JSON files; these are
# only the labels around it. Placeholders use str.format names.
UI: dict[str, dict[str, str]] = {
    "en": {
        "lang_badge": "EN",
        "lang_name": "English",
        "site_title": "ICF ACC Mock Exam",
        "brand_sub": "Mock Exam",
        "nav_tests": "Tests",
        "nav_admin": "Admin",
        "picker_title": "Select a Test",
        "picker_sub": "Choose an exam to begin a timed session: two sections of 30 questions, 39 minutes each, with a 10-minute break. Pass mark is 70%.",
        "admin_picker_title": "Browse Tests",
        "admin_picker_sub": "View all questions with correct answers and explanations.",
        "empty": "No test files found.",
        "empty_hint": "Run generate.py to create exam files.",
        "start": "Start Test",
        "browse": "Browse",
        "card_meta": "{n} questions · 2 sections × 39 min",
        "part": "Section {n}",
        "progress": "{a} / {total} answered",
        "leave_early": "Leave Early",
        "submit_section": "Submit Section",
        "next_section": "Next Section →",
        "break": "Break",
        "break_time": "Break time",
        "section1_complete": "Section 1 Complete",
        "answers_saved": "Your answers have been saved.",
        "continue_s2": "Continue to Section 2 →",
        "submit_test": "Submit Test",
        "confirm_one": "1 question is unanswered and will be marked incorrect. Submit anyway?",
        "confirm_many": "{n} questions are unanswered and will be marked incorrect. Submit anyway?",
        "results_title": "Results",
        "passed": "PASSED",
        "failed": "FAILED",
        "stat_correct": "{n} correct",
        "stat_wrong": "{n} wrong",
        "stat_unanswered": "{n} unanswered",
        "pass_requires": "Pass requires {p}/{total} (70%)",
        "back": "← Back to Tests",
        "breakdown": "Question Breakdown",
        "q_correct": "Correct",
        "q_wrong": "Wrong",
        "q_unanswered": "Unanswered",
        "marker_correct": "Correct",
        "marker_yours": "Your answer",
        "explanation": "Explanation",
        "admin_prefix": "Admin",
        "all_tests": "← All Tests",
        "n_questions": "{n} questions",
    },
    "uk": {
        "lang_badge": "UA",
        "lang_name": "Українська",
        "site_title": "Пробний іспит ICF ACC",
        "brand_sub": "Пробний іспит",
        "nav_tests": "Тести",
        "nav_admin": "Адмін",
        "picker_title": "Оберіть тест",
        "picker_sub": "Іспит із таймером: дві частини по 30 питань, по 39 хвилин на кожну, з 10-хвилинною перервою. Прохідний бал — 70%.",
        "admin_picker_title": "Перегляд тестів",
        "admin_picker_sub": "Усі питання з правильними відповідями та поясненнями.",
        "empty": "Тестів поки немає.",
        "empty_hint": "Запустіть generate.py, щоб створити тести.",
        "start": "Почати тест",
        "browse": "Переглянути",
        "card_meta": "{n} {questions_word} · 2 частини × 39 хв",
        "part": "Частина {n}",
        "progress": "Відповідей: {a} / {total}",
        "leave_early": "Завершити достроково",
        "submit_section": "Завершити частину",
        "next_section": "Наступна частина →",
        "break": "Перерва",
        "break_time": "Час перерви",
        "section1_complete": "Частину 1 завершено",
        "answers_saved": "Ваші відповіді збережено.",
        "continue_s2": "Перейти до частини 2 →",
        "submit_test": "Завершити тест",
        "confirm_one": "Питань без відповіді: 1. Вони будуть зараховані як неправильні. Завершити тест?",
        "confirm_many": "Питань без відповіді: {n}. Вони будуть зараховані як неправильні. Завершити тест?",
        "results_title": "Результати",
        "passed": "СКЛАДЕНО",
        "failed": "НЕ СКЛАДЕНО",
        "stat_correct": "Правильно: {n}",
        "stat_wrong": "Неправильно: {n}",
        "stat_unanswered": "Без відповіді: {n}",
        "pass_requires": "Прохідний бал: {p}/{total} (70%)",
        "back": "← До списку тестів",
        "breakdown": "Розбір питань",
        "q_correct": "Правильно",
        "q_wrong": "Неправильно",
        "q_unanswered": "Без відповіді",
        "marker_correct": "Правильна",
        "marker_yours": "Ваша відповідь",
        "explanation": "Пояснення",
        "admin_prefix": "Адмін",
        "all_tests": "← Усі тести",
        "n_questions": "{n} {questions_word}",
    },
}

# Strings the exam page's JavaScript needs.
_JS_KEYS = (
    "part", "progress", "next_section", "submit_section",
    "break", "break_time", "confirm_one", "confirm_many",
)


def _questions_word(n: int, lang: str) -> str:
    if lang != "uk":
        return "questions"
    if n % 10 == 1 and n % 100 != 11:
        return "питання"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "питання"
    return "питань"


def _fmt(lang: str, key: str, **kwargs) -> str:
    if "n" in kwargs:
        kwargs.setdefault("questions_word", _questions_word(kwargs["n"], lang))
    return UI[lang][key].format(**kwargs)


def _ui_lang() -> str:
    """Pick the interface language: ?lang= → cookie → browser → default."""
    for candidate in (request.args.get("lang"), request.cookies.get(LANG_COOKIE)):
        if candidate in UI:
            return candidate
    return request.accept_languages.best_match(list(UI), default=DEFAULT_LANG)


def _render(template: str, lang: str, **ctx):
    return render_template(
        template,
        lang=lang,
        t=UI[lang],
        ui=UI,
        fmt=lambda key, **kw: _fmt(lang, key, **kw),
        fmt_in=_fmt,
        **ctx,
    )


@app.template_filter("fmt_filename")
def fmt_filename(filename: str) -> str:
    name = filename.removesuffix(".json")
    try:
        dt = datetime.strptime(name, "%Y-%m-%dT%H-%M-%S")
        return dt.strftime("%b %-d, %Y · %H:%M")
    except ValueError:
        return filename


def _read_exam(filename: str) -> dict:
    with (JSONS_DIR / filename).open(encoding="utf-8") as f:
        return json.load(f)


def _exam_info(filename: str, data: dict) -> dict:
    meta = data.get("meta") or {}
    lang = meta.get("language")
    return {
        "filename": filename,
        "title": meta.get("title") or fmt_filename(filename),
        "description": meta.get("description", ""),
        "lang": lang if lang in UI else DEFAULT_LANG,
        "order": meta.get("order", 1000),
        "count": len(data["mock_exam_batch"]),
    }


def _list_exams(lang: str | None = None) -> list[dict]:
    exams = []
    for path in JSONS_DIR.glob("*.json"):
        try:
            info = _exam_info(path.name, _read_exam(path.name))
        except (KeyError, TypeError, json.JSONDecodeError, OSError):
            continue
        if lang is None or info["lang"] == lang:
            exams.append(info)
    # Explicit order first; files without one (raw generator output) newest first.
    exams.sort(key=lambda e: e["filename"], reverse=True)
    exams.sort(key=lambda e: (e["order"], e["lang"]))
    return exams


def _load_exam(filename: str) -> tuple[dict, list[dict]]:
    data = _read_exam(filename)
    return _exam_info(filename, data), data["mock_exam_batch"]


def _picker(admin: bool):
    lang = _ui_lang()
    exams = _list_exams(None if admin else lang)
    resp = app.make_response(
        _render("serve/picker.html", lang, exams=exams, admin=admin, lang_switch=True)
    )
    if request.args.get("lang") in UI:
        resp.set_cookie(LANG_COOKIE, lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@app.route("/ping")
def ping():
    return "", 204


@app.route("/")
def picker():
    return _picker(admin=False)


@app.route("/test/<filename>")
def test(filename: str):
    try:
        info, questions = _load_exam(filename)
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
    lang = info["lang"]
    t_js = {key: UI[lang][key] for key in _JS_KEYS}
    return _render(
        "serve/test.html", lang, questions=safe, filename=filename, exam=info, t_js=t_js
    )


@app.route("/submit/<filename>", methods=["POST"])
def submit(filename: str):
    try:
        info, questions = _load_exam(filename)
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
        "exam": info,
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
    return _render("serve/results.html", data["exam"]["lang"], **data)


@app.route("/admin")
def admin_picker():
    return _picker(admin=True)


@app.route("/admin/<filename>")
def admin_view(filename: str):
    try:
        info, questions = _load_exam(filename)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return redirect(url_for("admin_picker"))
    return _render(
        "serve/admin.html", info["lang"],
        questions=questions, filename=filename, exam=info, admin=True,
    )


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
