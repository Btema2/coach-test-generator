# ICF ACC Domain Blueprint & EN/UK Mapping

## 60-Question Domain Split (ACC Exam Content Outline)

| Domain | Share | Count (60 Q) | `competency_reference` Prefix (EN) |
| :--- | :---: | :---: | :--- |
| Coaching Ethics | 30% | 18 | `Code of Ethics Section <1-5>: ...` |
| Definition & Boundaries | 30% | 18 | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. ...` |
| Coaching Competencies 2–8 | 40% | 24 | `Core Competency <2-8>: <Name>` |

Recommended Competency 2–8 breakdown across the 24 items:
- `Core Competency 2` (Embodies a Coaching Mindset): 3–4
- `Core Competency 3` (Establishes and Maintains Agreements): 4
- `Core Competency 4` (Cultivates Trust and Safety): 3
- `Core Competency 5` (Maintains Presence): 3
- `Core Competency 6` (Listens Actively): 3–4
- `Core Competency 7` (Evokes Awareness): 4
- `Core Competency 8` (Facilitates Client Growth): 3–4

Balance `is_correct` across `A`, `B`, `C`, `D` evenly (`15 / 15 / 15 / 15` for 60 items).

## Canonical `competency_reference` Strings

`serve.py`'s `_area()` matches `Core Competency (\d+)` / `Ключова компетенція (\d+)` before checking for `ethic` / `етичн`, and extracts the area display name from the text between `:` and ` — `. Keep the base names exact:

| Area Key | English (`competency_reference`) | Ukrainian (`competency_reference`) |
| :--- | :--- | :--- |
| `ethics` | `Code of Ethics Section 1: Agreements` | `Етичний кодекс ICF, розділ 1: Домовленості` |
| `ethics` | `Code of Ethics Section 2: Confidentiality & Legal Compliance` | `Етичний кодекс ICF, розділ 2: Конфіденційність і правові вимоги` |
| `ethics` | `Code of Ethics Section 3: Professional Conduct & Conflicts of Interest` | `Етичний кодекс ICF, розділ 3: Професійна поведінка та конфлікт інтересів` |
| `ethics` | `Code of Ethics Section 4: Commitment to Delivering Consistent Value` | `Етичний кодекс ICF, розділ 4: Стабільна цінність коучингу` |
| `ethics` | `Code of Ethics Section 5: Professional Integrity & Accountability` | `Етичний кодекс ICF, розділ 5: Професійна доброчесність і підзвітність` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Therapy` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і терапія` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Consulting` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і консалтинг` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Mentoring` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і менторство` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Training` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і навчання` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Management` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і управління` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Friendship` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і дружба` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Medical Advice` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і медична допомога` |
| `cc1` | `Core Competency 1: Demonstrates Ethical Practice — Coaching vs. Advocacy` | `Ключова компетенція 1: Демонструє етичну практику — коучинг і представництво інтересів` |
| `cc2` | `Core Competency 2: Embodies a Coaching Mindset` | `Ключова компетенція 2: Втілює коучингове мислення` |
| `cc3` | `Core Competency 3: Establishes and Maintains Agreements` | `Ключова компетенція 3: Встановлює та підтримує домовленості` |
| `cc4` | `Core Competency 4: Cultivates Trust and Safety` | `Ключова компетенція 4: Розвиває довіру та безпеку` |
| `cc5` | `Core Competency 5: Maintains Presence` | `Ключова компетенція 5: Підтримує присутність` |
| `cc6` | `Core Competency 6: Listens Actively` | `Ключова компетенція 6: Активно слухає` |
| `cc7` | `Core Competency 7: Evokes Awareness` | `Ключова компетенція 7: Пробуджує усвідомлення` |
| `cc8` | `Core Competency 8: Facilitates Client Growth` | `Ключова компетенція 8: Сприяє зростанню клієнта` |

Note: `tests/test_serve.py` checks `Core Competency 7: Evokes Awareness` in `set-2-en.json` and expects `Evokes Awareness` as the extracted area name. Also preserve matching first digits (`\d`) between EN and UK `competency_reference` entries on every question pair.

## Published `meta` Block Format

```json
{
  "meta": {
    "title": "ACC Mock Exam — Set 1",
    "description": "60 scenario-based questions on the 2025 ICF Core Competencies, coaching boundaries, and Code of Ethics.",
    "language": "en",
    "order": 1
  },
  "mock_exam_batch": []
}
```
