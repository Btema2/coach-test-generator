import argparse
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import i18n
from i18n import DEFAULT_LANG, UI
from i18n import questions_word as _questions_word  # noqa: F401  (re-exported for tests)
from store import Store

# `neon deploy` / `neon env pull` write DATABASE_URL to .env.local; it takes precedence over .env.
load_dotenv(Path(__file__).with_name(".env.local"))
load_dotenv()

ROOT = Path(__file__).parent
JSONS_DIR = ROOT / "jsons"

SECTION_SIZE = 30
SECTION_SECONDS = 39 * 60
BREAK_SECONDS = 10 * 60
LANG_COOKIE = "lang"
BRAND = os.getenv("BRAND_NAME", "").strip() or "Coach Exam Prep"
LEGAL_UPDATED = datetime(2026, 11, 25)
USERNAME_RE = re.compile(r"\w[\w.\-]{2,31}")  # letters, digits, . _ -; 3–32 chars
PASSWORD_MIN = 8
FILENAME_RE = re.compile(r"[\w.\-]+\.json")
OPTION_IDS = {"A", "B", "C", "D"}
CSRF_EXEMPT = {"submit", "api_check", "static"}

app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),
)


def _env_public_url() -> str:
    return (os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")


app.config["SESSION_COOKIE_SECURE"] = _env_public_url().startswith("https://")


# ── Storage ──

def init_store(url: str | None = None) -> Store:
    url = url or os.getenv("DATABASE_URL") or f"sqlite:///{ROOT / 'data' / 'app.db'}"
    store = Store(url)
    app.extensions["store"] = store
    app.secret_key = os.getenv("SECRET_KEY") or store.get_or_create_setting(
        "secret_key", lambda: secrets.token_hex(32)
    )
    return store


def _store() -> Store:
    return app.extensions.get("store") or init_store()


# ── Language ──

def _fmt(lang: str, key: str, **kwargs) -> str:
    kwargs.setdefault("brand", BRAND)
    return i18n.fmt(lang, key, **kwargs)


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
        return dt.strftime("%b %-d, %Y, %H:%M")
    except ValueError:
        return filename


# ── Exams ──

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


def _load_exam(filename: str) -> tuple[dict, list[dict]] | None:
    if not FILENAME_RE.fullmatch(filename):
        return None
    try:
        data = _read_exam(filename)
        return _exam_info(filename, data), data["mock_exam_batch"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _public_question(q: dict) -> dict:
    """A question without its answer key."""
    return {
        "question_id": str(q["question_id"]),
        "scenario_question": q["scenario_question"],
        "options": [{"id": o["id"], "text": o["text"]} for o in q["options"]],
    }


def _correct_id(q: dict) -> str:
    return next(o["id"] for o in q["options"] if o["is_correct"])


# ── Competency areas ──

_CC_RE = re.compile(r"(?:Core Competency|Ключова компетенція)\s*(\d+)", re.IGNORECASE)
_ETHICS_RE = re.compile(r"ethic|етичн", re.IGNORECASE)


def _area(ref: str, lang: str) -> dict:
    """Group a competency reference into a scoring area (one per competency, one for ethics)."""
    head = ref.split(" — ")[0].strip()
    m = _CC_RE.search(ref)
    if m:
        n = int(m.group(1))
        prefix, _, name = head.partition(":")
        return {"key": f"cc{n}", "order": n, "name": name.strip() or head, "group": prefix.strip()}
    if _ETHICS_RE.search(ref):
        return {"key": "ethics", "order": 0, "name": UI[lang]["area_ethics"], "group": ""}
    return {"key": "other", "order": 99, "name": head, "group": ""}


def _area_scores(graded: list[dict], lang: str) -> list[dict]:
    areas: dict[str, dict] = {}
    for r in graded:
        a = _area(r["competency_reference"], lang)
        s = areas.setdefault(a["key"], {**a, "correct": 0, "total": 0})
        s["total"] += 1
        s["correct"] += int(r["ok"])
    scores = list(areas.values())
    for s in scores:
        s["pct"] = round(s["correct"] / s["total"] * 100)
    scores.sort(key=lambda s: (s["pct"], s["order"]))
    return scores


# ── Grading ──

def _pass_score(total: int) -> int:
    return -(-total * 7 // 10)  # ceil(70%)


def _grade(questions: list[dict], answers: dict[str, str]) -> list[dict]:
    graded = []
    for q in questions:
        qid = str(q["question_id"])
        correct = _correct_id(q)
        selected = answers.get(qid)
        graded.append(
            {
                "question_id": qid,
                "competency_reference": q["competency_reference"],
                "scenario_question": q["scenario_question"],
                "options": q["options"],
                "selected": selected,
                "correct": correct,
                "ok": selected == correct,
                "unanswered": selected is None,
                "rationale": q["ai_rationale"]["explanation"],
            }
        )
    return graded


# ── Accounts and sessions ──

def _owner() -> dict:
    if g.user:
        return {"user_id": g.user["id"]}
    return {"guest_id": session.get("guest_id")}


def _ensure_guest_id() -> str:
    if not session.get("guest_id"):
        session["guest_id"] = secrets.token_hex(16)
        session.permanent = True
    return session["guest_id"]


def _guest_free_exams() -> int | None:
    raw = os.getenv("GUEST_FREE_EXAMS", "1").strip()
    try:
        n = int(raw)
    except ValueError:
        return 1
    return None if n < 0 else n


def _guest_gated() -> bool:
    """Guests must sign in after their free exams."""
    if g.user:
        return False
    limit = _guest_free_exams()
    if limit is None:
        return False
    return _store().count_attempts(guest_id=session.get("guest_id")) >= limit


def _safe_next(target: str | None) -> str | None:
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


def _csrf_token() -> str:
    token = session.get("csrf")
    if not token:
        token = session["csrf"] = secrets.token_urlsafe(24)
    return token


def _admin_enabled() -> bool:
    return bool(os.getenv("ADMIN_PASSWORD"))


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _admin_enabled():
            abort(404)
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


_CSRF_FALLBACK = {
    "login": "login",
    "register": "register",
    "admin_login": "admin_login",
    "account_delete": "account",
}


@app.before_request
def _load_request_state():
    if request.endpoint == "static":
        return None
    store = _store()
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = store.get_user(user_id)
        if g.user is None:
            session.pop("user_id", None)

    if request.method == "POST" and request.endpoint not in CSRF_EXEMPT:
        sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token") or ""
        expected = session.get("csrf") or ""
        if not expected or not hmac.compare_digest(sent, expected):
            flash(UI[_ui_lang()]["csrf_failed"])
            target = _CSRF_FALLBACK.get(request.endpoint or "", "landing")
            return redirect(url_for(target))


@app.after_request
def _after(resp):
    if request.args.get("lang") in UI:
        resp.set_cookie(LANG_COOKIE, request.args["lang"], max_age=60 * 60 * 24 * 365, samesite="Lax")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp


@app.context_processor
def _globals():
    def asset(path: str) -> str:
        try:
            version = int((ROOT / "static" / path).stat().st_mtime)
        except OSError:
            version = 0
        return url_for("static", filename=path, v=version)

    def switch_lang_url(lang: str) -> str:
        return url_for(request.endpoint, lang=lang, **(request.view_args or {}))

    return {
        "brand": BRAND,
        "user": g.get("user"),
        "asset": asset,
        "csrf_token": _csrf_token,
        "switch_lang_url": switch_lang_url,
        "is_admin": bool(session.get("admin")) and _admin_enabled(),
        "contact_email": os.getenv("CONTACT_EMAIL", "").strip(),
        "public_base": _env_public_url(),
        "year": datetime.now().year,
    }


# ── Pages ──

def _sample_question(lang: str) -> tuple[dict, dict] | None:
    """A mid-length question from the first exam in this language, for the landing page."""
    for info in _list_exams(lang):
        loaded = _load_exam(info["filename"])
        if not loaded:
            continue
        _, questions = loaded
        fitting = [q for q in questions if 280 <= len(q["scenario_question"]) <= 520]
        q = (fitting or questions)[0]
        return info, _public_question(q)
    return None


@app.route("/ping")
def ping():
    return "", 204


@app.route("/robots.txt")
def robots():
    body = "User-agent: *\n" + "".join(
        f"Disallow: {p}\n" for p in ("/admin", "/results/", "/test/", "/login", "/register", "/account")
    )
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/")
def landing():
    lang = _ui_lang()
    exams = _list_exams(lang)
    sample = _sample_question(lang)
    return _render(
        "serve/landing.html", lang,
        exams=exams,
        sample_exam=sample[0] if sample else None,
        sample=sample[1] if sample else None,
        lang_switch=True,
    )


def _exam_stats(history: list[dict]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for a in history:
        pct = round(a["score"] / a["total"] * 100) if a["total"] else 0
        s = stats.setdefault(a["filename"], {"best": pct, "count": 0})
        s["best"] = max(s["best"], pct)
        s["count"] += 1
    return stats


def _progress_chart(history: list[dict], lang: str) -> dict | None:
    """Score-over-time line chart, oldest → newest, in 0–100 plot coordinates.

    x runs left → right and y top → bottom (y=0 is 100%), so the template can
    place HTML labels and dots with percentages and stretch the SVG line to fit.
    """
    points = list(reversed(history[:12]))
    if len(points) < 2:
        return None
    step = 100 / (len(points) - 1)
    out = []
    for i, a in enumerate(points):
        pct = round(a["score"] / a["total"] * 100) if a["total"] else 0
        out.append(
            {
                "x": round(i * step, 2),
                "y": 100 - pct,
                "pct": pct,
                "date": i18n.format_date(a["created_at"], lang),
                "title": a["exam_title"],
                "id": a["id"],
            }
        )
    return {
        "points": out,
        "path": " ".join(f"{'M' if i == 0 else 'L'}{p['x']},{p['y']}" for i, p in enumerate(out)),
        "ticks": (100, 50, 0),
    }


@app.route("/exams")
def exams():
    lang = _ui_lang()
    exam_list = _list_exams(lang)
    history = _store().list_attempts(**_owner())
    recent = [dict(a, date=i18n.format_date(a["created_at"], lang)) for a in history[:8]]
    return _render(
        "serve/exams.html", lang,
        exams=exam_list,
        stats=_exam_stats(history),
        recent=recent,
        chart=_progress_chart(history, lang),
        lang_switch=True,
        pass_score=_pass_score,
    )


@app.route("/test/<filename>")
def test(filename: str):
    loaded = _load_exam(filename)
    if not loaded:
        return redirect(url_for("exams"))
    if _guest_gated():
        return redirect(url_for("login", next=request.path, reason="gate"))
    info, questions = loaded
    lang = info["lang"]
    public = [_public_question(q) for q in questions]
    config = {
        "storageKey": f"exam:v1:{filename}",
        "sectionSize": SECTION_SIZE,
        "sectionSeconds": SECTION_SECONDS,
        "breakSeconds": BREAK_SECONDS,
        "total": len(public),
        "t": {key: UI[lang][key] for key in i18n.EXAM_JS_KEYS},
    }
    return _render(
        "serve/test.html", lang,
        questions=public, filename=filename, exam=info, config=config,
        section_size=SECTION_SIZE,
    )


@app.route("/submit/<filename>", methods=["POST"])
def submit(filename: str):
    loaded = _load_exam(filename)
    if not loaded:
        return redirect(url_for("exams"))
    info, questions = loaded

    valid_ids = {str(q["question_id"]) for q in questions}
    answers = {
        key[2:]: val
        for key, val in request.form.items()
        if key.startswith("q_") and key[2:] in valid_ids and val in OPTION_IDS
    }
    try:
        elapsed = int(request.form.get("elapsed_seconds", ""))
        max_elapsed = 2 * SECTION_SECONDS + BREAK_SECONDS
        elapsed = elapsed if 0 < elapsed <= max_elapsed else None
    except ValueError:
        elapsed = None

    graded = _grade(questions, answers)
    owner = _owner()
    if not g.user:
        owner = {"guest_id": _ensure_guest_id()}
    attempt_id = _store().save_attempt(
        filename=filename,
        exam_title=info["title"],
        lang=info["lang"],
        score=sum(r["ok"] for r in graded),
        total=len(graded),
        answers=answers,
        elapsed_seconds=elapsed,
        user_id=owner.get("user_id"),
        guest_id=owner.get("guest_id"),
    )
    return redirect(url_for("results", token=attempt_id))


def _next_exam(info: dict, owner_history: list[dict]) -> dict | None:
    others = [e for e in _list_exams(info["lang"]) if e["filename"] != info["filename"]]
    if not others:
        return None
    taken = {a["filename"] for a in owner_history}
    return next((e for e in others if e["filename"] not in taken), others[0])


@app.route("/results/<token>")
def results(token: str):
    attempt = _store().get_attempt(token)
    loaded = _load_exam(attempt["filename"]) if attempt else None
    if not loaded:
        return redirect(url_for("exams"))
    info, questions = loaded
    lang = info["lang"]
    graded = _grade(questions, attempt["answers"])
    total = len(graded)
    score = sum(r["ok"] for r in graded)
    unanswered = sum(r["unanswered"] for r in graded)
    pass_score = _pass_score(total)
    areas = _area_scores(graded, lang)
    weak = next((a for a in areas if a["pct"] < 70), None)
    elapsed = attempt.get("elapsed_seconds")
    is_owner = bool(
        (g.user and attempt["user_id"] == g.user["id"])
        or (attempt["guest_id"] and attempt["guest_id"] == session.get("guest_id"))
    )
    return _render(
        "serve/results.html", lang,
        exam=info,
        filename=info["filename"],
        token=token,
        graded=graded,
        score=score,
        total=total,
        wrong=total - score - unanswered,
        unanswered=unanswered,
        passed=score >= pass_score,
        pass_score=pass_score,
        short_by=max(0, pass_score - score),
        score_pct=round(score / total * 100) if total else 0,
        section1_score=sum(r["ok"] for r in graded[:SECTION_SIZE]),
        section2_score=sum(r["ok"] for r in graded[SECTION_SIZE:]),
        minutes=max(1, round(elapsed / 60)) if elapsed else None,
        areas=areas,
        weak_area=weak,
        next_exam=_next_exam(info, _store().list_attempts(**_owner())),
        show_save=is_owner and not g.user,
    )


@app.route("/practice/<filename>")
def practice(filename: str):
    loaded = _load_exam(filename)
    if not loaded:
        return redirect(url_for("exams"))
    info, questions = loaded
    lang = info["lang"]
    area_key = request.args.get("area", "")
    area = None
    if area_key:
        matching = [q for q in questions if _area(q["competency_reference"], lang)["key"] == area_key]
        if matching:
            questions = matching
            area = _area(matching[0]["competency_reference"], lang)
    config = {
        "checkUrl": url_for("api_check", filename=filename, qid="__QID__"),
        "t": {key: UI[lang][key] for key in i18n.PRACTICE_JS_KEYS},
    }
    return _render(
        "serve/practice.html", lang,
        exam=info, filename=filename, questions=[_public_question(q) for q in questions],
        area=area, config=config,
    )


@app.route("/api/check/<filename>/<qid>", methods=["POST"])
def api_check(filename: str, qid: str):
    loaded = _load_exam(filename)
    if not loaded:
        abort(404)
    _, questions = loaded
    q = next((q for q in questions if str(q["question_id"]) == qid), None)
    if q is None:
        abort(404)
    answer = (request.get_json(silent=True) or {}).get("answer")
    correct = _correct_id(q)
    return jsonify(
        correct=correct,
        ok=answer == correct,
        explanation=q["ai_rationale"]["explanation"],
    )


# ── Sign in ──

def _sign_in(user: dict, lang: str, next_url: str | None):
    store = _store()
    store.touch_login(user["id"])
    guest_id = session.pop("guest_id", None)
    session["user_id"] = user["id"]
    session.permanent = True
    flash(_fmt(lang, "signed_in", username=user["username"]))
    if guest_id and store.claim_guest_attempts(guest_id, user["id"]):
        flash(UI[lang]["results_claimed"])
    return redirect(next_url or url_for("exams"))


@app.route("/login", methods=["GET", "POST"])
def login():
    lang = _ui_lang()
    next_url = _safe_next(request.values.get("next"))
    if g.user:
        return redirect(next_url or url_for("exams"))

    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip().casefold()
        password = request.form.get("password", "")
        user = _store().get_user_by_username(username) if username else None
        if user and check_password_hash(user["password_hash"], password):
            return _sign_in(user, lang, next_url)
        error = UI[lang]["login_wrong"]

    return _render(
        "serve/login.html", lang,
        mode="login",
        errors={"password": error} if error else {},
        username=username,
        next_url=next_url,
        gate=request.args.get("reason") == "gate",
        lang_switch=True,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    lang = _ui_lang()
    t = UI[lang]
    next_url = _safe_next(request.values.get("next"))
    if g.user:
        return redirect(next_url or url_for("exams"))

    errors: dict[str, str] = {}
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip().casefold()
        password = request.form.get("password", "")
        if not USERNAME_RE.fullmatch(username):
            errors["username"] = t["username_invalid"]
        if len(password) < PASSWORD_MIN:
            errors["password"] = t["password_short"]
        elif password != request.form.get("password2", ""):
            errors["password2"] = t["password_mismatch"]
        if not errors:
            user = _store().create_user(username, generate_password_hash(password))
            if user:
                return _sign_in(user, lang, next_url)
            errors["username"] = t["username_taken"]

    return _render(
        "serve/login.html", lang,
        mode="register",
        errors=errors,
        username=username,
        next_url=next_url,
        gate=False,
        lang_switch=True,
    )


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash(UI[_ui_lang()]["signed_out"])
    return redirect(url_for("landing"))


@app.route("/account")
def account():
    if not g.user:
        return redirect(url_for("login", next=request.path))
    return _render("serve/account.html", _ui_lang(), lang_switch=True)


@app.route("/account/delete", methods=["POST"])
def account_delete():
    if not g.user:
        return redirect(url_for("login"))
    lang = _ui_lang()
    if request.form.get("confirm") != "yes":
        return redirect(url_for("account"))
    _store().delete_user(g.user["id"])
    session.clear()
    flash(UI[lang]["deleted"])
    return redirect(url_for("landing"))


# ── Legal ──

@app.route("/privacy")
def privacy():
    lang = _ui_lang()
    return _render(
        "serve/legal.html", lang, page="privacy",
        updated=i18n.format_date(LEGAL_UPDATED, lang), lang_switch=True,
    )


@app.route("/terms")
def terms():
    lang = _ui_lang()
    return _render(
        "serve/legal.html", lang, page="terms",
        updated=i18n.format_date(LEGAL_UPDATED, lang), lang_switch=True,
    )


# ── Answer key (owner only) ──

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not _admin_enabled():
        abort(404)
    lang = _ui_lang()
    next_url = _safe_next(request.values.get("next"))
    error = None
    if request.method == "POST":
        sent = request.form.get("password", "").encode()
        if hmac.compare_digest(sent, os.environ["ADMIN_PASSWORD"].encode()):
            session["admin"] = True
            return redirect(next_url or url_for("admin_picker"))
        time.sleep(1)  # slow down guessing
        error = UI[lang]["admin_wrong"]
    return _render("serve/admin_login.html", lang, error=error, next_url=next_url)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("landing"))


@app.route("/admin")
@admin_required
def admin_picker():
    lang = _ui_lang()
    return _render("serve/admin_index.html", lang, exams=_list_exams(None), lang_switch=True)


@app.route("/admin/<filename>")
@admin_required
def admin_view(filename: str):
    loaded = _load_exam(filename)
    if not loaded:
        return redirect(url_for("admin_picker"))
    info, questions = loaded
    return _render("serve/admin.html", info["lang"], questions=questions, filename=filename, exam=info)


@app.errorhandler(404)
def not_found(_err):
    lang = _ui_lang()
    return _render("serve/not_found.html", lang), 404


def main() -> None:
    parser = argparse.ArgumentParser(description="ICF ACC practice exam server")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    init_store()

    url = f"http://localhost:{args.port}"
    print(f"\n  Local:   {url}")
    print(f"  Network: accessible on port {args.port}")
    print()

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
