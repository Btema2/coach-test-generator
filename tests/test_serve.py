import html as html_lib
import json
import re

import pytest

import i18n
import serve
from serve import JSONS_DIR, UI, _questions_word, app

EXAM_FILES = sorted(p.name for p in JSONS_DIR.glob("*.json"))
CSRF = "test-csrf-token"


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'app.db'}"


@pytest.fixture
def client(db_url, monkeypatch):
    for var in ("DATABASE_URL", "ADMIN_PASSWORD", "PUBLIC_URL", "RENDER_EXTERNAL_URL"):
        monkeypatch.delenv(var, raising=False)
    app.config.update(TESTING=True, MAIL_CONSOLE=False)
    serve.init_store(db_url)
    with app.test_client() as c:
        yield c
    app.extensions.pop("store", None)


def _exam(filename: str) -> dict:
    return json.loads((JSONS_DIR / filename).read_text(encoding="utf-8"))


def _by_lang(lang: str) -> list[str]:
    return [f for f in EXAM_FILES if (_exam(f).get("meta") or {}).get("language", "en") == lang]


def _set_csrf(client):
    with client.session_transaction() as s:
        s["csrf"] = CSRF


def _correct_answers(filename: str, count: int) -> dict:
    questions = _exam(filename)["mock_exam_batch"]
    return {
        f"q_{q['question_id']}": next(o["id"] for o in q["options"] if o["is_correct"])
        for q in questions[:count]
    }


def _submit(client, filename: str, count: int, **extra) -> str:
    resp = client.post(f"/submit/{filename}", data={**_correct_answers(filename, count), **extra})
    assert resp.status_code == 302
    return resp.headers["Location"]


PASSWORD = "correct horse battery"


def _register(client, username="coach", password=PASSWORD, next_url=None, password2=None):
    _set_csrf(client)
    data = {"username": username, "password": password, "password2": password if password2 is None else password2, "csrf": CSRF}
    if next_url:
        data["next"] = next_url
    return client.post("/register?lang=en", data=data)


def _login(client, username="coach", password=PASSWORD, next_url=None):
    _set_csrf(client)
    data = {"username": username, "password": password, "csrf": CSRF}
    if next_url:
        data["next"] = next_url
    return client.post("/login?lang=en", data=data)


# ── Exam content ──

@pytest.mark.parametrize("filename", EXAM_FILES)
def test_exam_file_is_valid(filename):
    data = _exam(filename)
    meta = data.get("meta", {})
    assert meta.get("language", "en") in UI
    questions = data["mock_exam_batch"]
    assert len(questions) == 60, "the exam UI splits into two sections of 30"
    ids = [q["question_id"] for q in questions]
    assert len(set(ids)) == len(ids)
    for q in questions:
        assert q["competency_reference"] and q["scenario_question"]
        assert [o["id"] for o in q["options"]] == ["A", "B", "C", "D"]
        assert sum(o["is_correct"] for o in q["options"]) == 1
        assert q["ai_rationale"]["explanation"]
        text = " ".join(o["text"] for o in q["options"]).lower()
        assert "all of the above" not in text and "none of the above" not in text


def test_translations_match_their_source_answer_keys():
    pairs = [("2026-06-15T19-30-29.json", "set-1-uk.json"), ("set-2-en.json", "set-2-uk.json")]
    for en_file, uk_file in pairs:
        en = _exam(en_file)["mock_exam_batch"]
        uk = _exam(uk_file)["mock_exam_batch"]
        assert len(en) == len(uk)
        for e, u in zip(en, uk):
            assert [o["is_correct"] for o in e["options"]] == [o["is_correct"] for o in u["options"]]
            assert re.search(r"\d", e["competency_reference"]).group() == re.search(
                r"\d", u["competency_reference"]
            ).group()


# ── Language ──

def test_questions_word_ukrainian_plurals():
    assert _questions_word(1, "uk") == "питання"
    assert _questions_word(3, "uk") == "питання"
    assert _questions_word(12, "uk") == "питань"
    assert _questions_word(60, "uk") == "питань"
    assert _questions_word(60, "en") == "questions"


def test_attempts_plural():
    assert i18n.fmt("uk", "status_attempts", n=1) == "1 спроба"
    assert i18n.fmt("uk", "status_attempts", n=3) == "3 спроби"
    assert i18n.fmt("uk", "status_attempts", n=11) == "11 спроб"
    assert i18n.fmt("en", "status_attempts", n=1) == "1 attempt"


def test_ui_languages_have_same_keys():
    assert UI["en"].keys() == UI["uk"].keys()


def test_ui_placeholders_match_between_languages():
    for key, en in UI["en"].items():
        assert set(re.findall(r"\{(\w+)\}", en)) == set(re.findall(r"\{(\w+)\}", UI["uk"][key])), key


def test_english_strings_have_no_cyrillic():
    assert [k for k, v in UI["en"].items() if re.search("[Ѐ-ӿ]", v)] == []


def test_exam_list_filters_by_lang_param(client):
    uk = client.get("/?lang=uk").get_data(as_text=True)
    assert "Пробні іспити" in uk
    for f in _by_lang("uk"):
        assert f in uk
    for f in _by_lang("en"):
        assert f not in uk

    en = client.get("/?lang=en").get_data(as_text=True)
    assert "ICF ACC practice exams" in en
    for f in _by_lang("uk"):
        assert f not in en


def test_lang_choice_is_remembered_in_cookie(client):
    client.get("/?lang=uk")
    assert '<html lang="uk">' in client.get("/").get_data(as_text=True)


def test_uses_browser_language(client):
    resp = client.get("/", headers={"Accept-Language": "uk-UA,uk;q=0.9,en;q=0.5"})
    assert '<html lang="uk">' in resp.get_data(as_text=True)


# ── Landing ──

def test_home_lists_exams_without_answers(client):
    html = client.get("/?lang=en").get_data(as_text=True)
    for f in _by_lang("en"):
        assert f"/test/{f}" in html and f"/practice/{f}" in html
    assert "is_correct" not in html
    assert "not affiliated with" in html
    assert "/admin" not in html


def test_old_exam_list_url_redirects_home(client):
    resp = client.get("/exams?lang=uk")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/?lang=uk")


def test_empty_state_has_no_developer_instructions(tmp_path, monkeypatch, client):
    monkeypatch.setattr(serve, "JSONS_DIR", tmp_path)
    html = client.get("/?lang=en").get_data(as_text=True)
    assert "There are no exams in this language yet." in html
    assert "generate.py" not in html


def test_exam_without_meta_falls_back_to_filename_and_english(tmp_path, monkeypatch, client):
    q = _exam("set-2-en.json")["mock_exam_batch"]
    (tmp_path / "2026-01-02T03-04-05.json").write_text(json.dumps({"mock_exam_batch": q}))
    monkeypatch.setattr(serve, "JSONS_DIR", tmp_path)
    html = client.get("/?lang=en").get_data(as_text=True)
    assert "Jan 2, 2026, 03:04" in html


# ── Exam flow ──

def test_ukrainian_exam_page_is_localized_and_hides_answers(client):
    filename = "set-2-uk.json"
    html = client.get(f"/test/{filename}").get_data(as_text=True)
    assert '<html lang="uk">' in html
    assert "Завершити перегляд" in html
    assert "End Review" not in html
    assert "is_correct" not in html
    first = _exam(filename)["mock_exam_batch"][0]
    assert first["ai_rationale"]["explanation"][:40] not in html


def test_english_exam_keeps_english_ui(client):
    html = client.get("/test/set-2-en.json").get_data(as_text=True)
    assert '<html lang="en">' in html
    assert "End Review" in html and "Item Review Screen" in html


def test_unknown_exam_redirects(client):
    assert client.get("/test/missing.json").status_code == 302
    assert client.get("/test/..").status_code == 302


def test_submit_grades_and_shows_localized_results(client):
    location = _submit(client, "set-2-uk.json", 45, elapsed_seconds="2400")
    html = client.get(location).get_data(as_text=True)
    assert "Іспит складено" in html
    assert "Правильних відповідей: 45 з 60" in html
    assert "<dd>15</dd>" in html  # unanswered
    assert "40 хв" in html
    assert "Перегляд відповідей" in html


def test_failed_result_says_how_far_from_passing(client):
    html = client.get(_submit(client, "set-2-en.json", 30)).get_data(as_text=True)
    assert "Not yet" in html
    assert "You need 42 to pass: 12 more correct answers." in html


def test_submit_ignores_unknown_questions_and_options(client):
    questions = _exam("set-2-en.json")["mock_exam_batch"]
    location = _submit(
        client, "set-2-en.json", 1,
        **{f"q_{questions[1]['question_id']}": "Z", "q_not-a-question": "A"},
    )
    attempt = serve._store().get_attempt(location.rsplit("/", 1)[1])
    assert list(attempt["answers"]) == [str(questions[0]["question_id"])]


def test_results_survive_a_restart(client, db_url):
    location = _submit(client, "set-2-en.json", 50)
    serve.init_store(db_url)  # a fresh store on the same database, as after a deploy
    assert "You passed" in client.get(location).get_data(as_text=True)


def test_unknown_results_token_redirects(client):
    assert client.get("/results/not-a-real-token").status_code == 302


def test_results_break_down_score_by_area_weakest_first(client):
    html = client.get(_submit(client, "set-2-en.json", 30)).get_data(as_text=True)
    pcts = [int(p) for p in re.findall(r'<span class="area-value">(\d+)%', html)]
    assert pcts and pcts == sorted(pcts)
    assert "Code of Ethics" in html


def test_area_grouping():
    a = serve._area("Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Therapy", "en")
    assert (a["key"], a["name"], a["group"]) == ("cc1", "Demonstrates Ethical Practice", "Core Competency 1")
    assert serve._area("Ключова компетенція 7: Пробуджує усвідомлення", "uk")["key"] == "cc7"
    assert serve._area("Code of Ethics Section 2: Confidentiality & Legal", "en")["key"] == "ethics"
    assert serve._area("Етичний кодекс ICF, розділ 2: Конфіденційність", "uk")["name"] == "Етичний кодекс ICF"


# ── Practice ──

def test_practice_check_returns_answer_and_explanation(client):
    q = _exam("set-2-en.json")["mock_exam_batch"][0]
    correct = next(o["id"] for o in q["options"] if o["is_correct"])
    resp = client.post(f"/api/check/set-2-en.json/{q['question_id']}", json={"answer": correct})
    assert resp.get_json() == {"correct": correct, "ok": True, "explanation": q["ai_rationale"]["explanation"]}
    assert client.post("/api/check/set-2-en.json/nope", json={"answer": "A"}).status_code == 404


def test_practice_page_hides_answers_and_filters_by_area(client):
    html = client.get("/practice/set-2-en.json?area=cc7").get_data(as_text=True)
    expected = sum(
        1 for q in _exam("set-2-en.json")["mock_exam_batch"]
        if q["competency_reference"].startswith("Core Competency 7")
    )
    assert html.count('class="pq"') == expected
    assert "is_correct" not in html
    assert "Showing only questions on Evokes Awareness." in html


# ── Answer key (owner only) ──

def test_answer_key_is_off_without_a_password(client):
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/set-1-uk.json").status_code == 404
    assert client.get("/admin/login").status_code == 404


def test_answer_key_needs_the_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    monkeypatch.setattr(serve.time, "sleep", lambda _s: None)
    resp = client.get("/admin/set-1-uk.json")
    assert resp.status_code == 302 and "/admin/login" in resp.headers["Location"]

    _set_csrf(client)
    wrong = client.post("/admin/login", data={"password": "nope", "csrf": CSRF})
    assert "That password isn't right." in html_lib.unescape(wrong.get_data(as_text=True))

    ok = client.post("/admin/login", data={"password": "s3cret", "csrf": CSRF, "next": "/admin/set-1-uk.json"})
    assert ok.headers["Location"].endswith("/admin/set-1-uk.json")
    html = client.get("/admin/set-1-uk.json").get_data(as_text=True)
    assert "Пояснення:" in html
    assert "Пробний іспит ACC — Варіант 1" in html
    index = client.get("/admin?lang=en").get_data(as_text=True)
    for f in EXAM_FILES:
        assert f in index


def test_no_admin_link_in_public_nav(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    html = client.get("/?lang=en").get_data(as_text=True)
    assert "/admin" not in html


# ── Accounts ──

def test_sign_in_link_in_nav_for_guests(client):
    assert ">Sign in<" in client.get("/?lang=en").get_data(as_text=True)


def test_guests_can_take_every_exam_without_an_account(client):
    _submit(client, "set-2-en.json", 10)
    _submit(client, "set-2-uk.json", 10)
    assert client.get("/test/2026-06-15T19-30-29.json").status_code == 200
    assert client.get("/test/set-1-uk.json").status_code == 200


def test_register_claims_guest_results(client):
    location = _submit(client, "set-2-en.json", 50)
    resp = _register(client, username="Coach.Anna", next_url=location)
    assert resp.status_code == 302 and resp.headers["Location"].endswith(location)

    html = client.get("/?lang=en").get_data(as_text=True)
    assert "coach.anna" in html  # signed in: the header shows the username
    assert "Best score 83%" in html
    user = serve._store().get_user_by_username("coach.anna")  # usernames are case-insensitive
    assert serve._store().count_attempts(user_id=user["id"]) == 1
    assert PASSWORD not in user["password_hash"] and user["password_hash"].startswith("scrypt:")


def test_sign_in_with_password(client):
    _register(client)
    client.post("/logout", data={"csrf": CSRF})
    assert client.get("/account").status_code == 302

    wrong = _login(client, password="not the password")
    assert wrong.status_code == 200
    assert "That username and password don't match." in html_lib.unescape(wrong.get_data(as_text=True))
    unknown = _login(client, username="nobody")
    assert "That username and password don't match." in html_lib.unescape(unknown.get_data(as_text=True))

    ok = _login(client, username="COACH")
    assert ok.status_code == 302 and ok.headers["Location"].endswith("/")
    assert "Signed in as coach" in client.get("/account?lang=en").get_data(as_text=True)


@pytest.mark.parametrize("kwargs, message", [
    ({"username": "ab"}, "Use 3–32 characters"),
    ({"username": "has space"}, "Use 3–32 characters"),
    ({"username": "x" * 33}, "Use 3–32 characters"),
    ({"password": "short"}, "Use at least 8 characters."),
    ({"password2": "something else"}, "The passwords don't match."),
])
def test_register_validates_input(client, kwargs, message):
    resp = _register(client, **kwargs)
    assert resp.status_code == 200
    assert message in html_lib.unescape(resp.get_data(as_text=True))
    assert serve._store().get_user_by_username(kwargs.get("username", "coach").casefold()) is None
    assert client.get("/account").status_code == 302


def test_register_rejects_taken_username(client):
    _register(client)
    client.post("/logout", data={"csrf": CSRF})
    resp = _register(client, username="Coach", password="another password")
    assert "That username is taken." in resp.get_data(as_text=True)
    assert client.get("/account").status_code == 302


def test_ukrainian_usernames_work(client):
    assert _register(client, username="коуч_олена").status_code == 302
    assert serve._store().get_user_by_username("коуч_олена") is not None


def test_sign_in_needs_csrf_token(client):
    resp = client.post("/register", data={"username": "coach", "password": PASSWORD, "password2": PASSWORD})
    assert resp.status_code == 302 and "/register" in resp.headers["Location"]
    assert serve._store().get_user_by_username("coach") is None


def test_sign_in_ignores_offsite_next(client):
    resp = _register(client, next_url="//evil.example/steal")
    assert resp.headers["Location"].endswith("/")
    assert "evil.example" not in resp.headers["Location"]


def test_delete_account_removes_results(client):
    _register(client)
    _submit(client, "set-2-en.json", 50)
    user = serve._store().get_user_by_username("coach")
    assert client.get("/account?lang=en").status_code == 200

    _set_csrf(client)
    resp = client.post("/account/delete", data={"csrf": CSRF, "confirm": "yes"})
    assert resp.status_code == 302
    assert serve._store().get_user(user["id"]) is None
    assert serve._store().count_attempts(user_id=user["id"]) == 0
    assert client.get("/account").status_code == 302


# ── Misc ──

def test_legal_pages_and_robots(client):
    assert "Who processes your data" in client.get("/privacy?lang=en").get_data(as_text=True)
    assert "Лише для підготовки" in client.get("/terms?lang=uk").get_data(as_text=True)
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /admin" in robots


def test_not_found_page(client):
    resp = client.get("/no-such-page?lang=en")
    assert resp.status_code == 404
    assert "Page not found" in resp.get_data(as_text=True)

