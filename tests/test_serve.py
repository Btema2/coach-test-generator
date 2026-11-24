import json
import re

import pytest

import serve
from serve import JSONS_DIR, UI, _questions_word, app

EXAM_FILES = sorted(p.name for p in JSONS_DIR.glob("*.json"))


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _exam(filename: str) -> dict:
    return json.loads((JSONS_DIR / filename).read_text(encoding="utf-8"))


def _by_lang(lang: str) -> list[str]:
    return [f for f in EXAM_FILES if (_exam(f).get("meta") or {}).get("language", "en") == lang]


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


# ── Language selection ──

def test_questions_word_ukrainian_plurals():
    assert _questions_word(1, "uk") == "питання"
    assert _questions_word(3, "uk") == "питання"
    assert _questions_word(12, "uk") == "питань"
    assert _questions_word(60, "uk") == "питань"
    assert _questions_word(60, "en") == "questions"


def test_ui_languages_have_same_keys():
    assert UI["en"].keys() == UI["uk"].keys()


def test_picker_filters_exams_by_lang_param(client):
    uk = client.get("/?lang=uk").get_data(as_text=True)
    assert "Оберіть тест" in uk
    for f in _by_lang("uk"):
        assert f in uk
    for f in _by_lang("en"):
        assert f not in uk

    en = client.get("/?lang=en").get_data(as_text=True)
    assert "Select a Test" in en
    for f in _by_lang("uk"):
        assert f not in en


def test_picker_remembers_lang_in_cookie(client):
    client.get("/?lang=uk")
    assert "Оберіть тест" in client.get("/").get_data(as_text=True)


def test_picker_uses_browser_language(client):
    resp = client.get("/", headers={"Accept-Language": "uk-UA,uk;q=0.9,en;q=0.5"})
    assert '<html lang="uk">' in resp.get_data(as_text=True)


def test_admin_picker_lists_all_languages(client):
    html = client.get("/admin?lang=en").get_data(as_text=True)
    for f in EXAM_FILES:
        assert f in html


# ── Exam flow ──

def test_ukrainian_exam_page_is_localized_and_hides_answers(client):
    filename = "set-2-uk.json"
    html = client.get(f"/test/{filename}").get_data(as_text=True)
    assert '<html lang="uk">' in html
    assert "Завершити достроково" in html
    assert "Leave Early" not in html
    assert "is_correct" not in html
    first = _exam(filename)["mock_exam_batch"][0]
    assert first["ai_rationale"]["explanation"][:40] not in html


def test_submit_grades_and_shows_localized_results(client):
    filename = "set-2-uk.json"
    questions = _exam(filename)["mock_exam_batch"]
    form = {}
    for q in questions[:45]:
        form[f"q_{q['question_id']}"] = next(o["id"] for o in q["options"] if o["is_correct"])
    resp = client.post(f"/submit/{filename}", data=form)
    assert resp.status_code == 302
    html = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "СКЛАДЕНО" in html
    assert "Правильно: 45" in html
    assert "Без відповіді: 15" in html
    assert "Розбір питань" in html


def test_english_exam_keeps_english_ui(client):
    html = client.get("/test/set-2-en.json").get_data(as_text=True)
    assert '<html lang="en">' in html
    assert "Leave Early" in html


def test_admin_view_uses_exam_language(client):
    html = client.get("/admin/set-1-uk.json").get_data(as_text=True)
    assert "Пояснення:" in html
    assert "Пробний іспит ACC — Варіант 1" in html


def test_unknown_exam_redirects_to_picker(client):
    resp = client.get("/test/missing.json")
    assert resp.status_code == 302


def test_exam_without_meta_falls_back_to_filename_and_english(tmp_path, monkeypatch, client):
    q = _exam("set-2-en.json")["mock_exam_batch"]
    (tmp_path / "2026-01-02T03-04-05.json").write_text(json.dumps({"mock_exam_batch": q}))
    monkeypatch.setattr(serve, "JSONS_DIR", tmp_path)
    html = client.get("/?lang=en").get_data(as_text=True)
    assert "Jan 2, 2026 · 03:04" in html
