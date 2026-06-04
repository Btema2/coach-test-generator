# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Python CLI that generates unique ICF ACC (Associate Certified Coach) mock exam questions using an AI model. Questions follow ICF Core Competencies (2019) and ICF Code of Ethics (2025/2026) and are output as structured JSON.

## Key File

**`ACC-test-prompt.md`** — The AI system prompt. Contains:
- `{{NUMBER_OF_QUESTIONS}}` — template variable for batch size
- `{{EXISTING_QUESTIONS_DB}}` — template variable injected with already-generated question IDs/topics to prevent duplication
- Psychometric rules, ICF knowledge bases, few-shot examples
- Output JSON schema (`mock_exam_batch` array)

## Architecture (to be built)

The script must:
1. Load and fill the prompt template (`ACC-test-prompt.md`) with real values
2. Maintain a local database of existing questions (to inject into `{{EXISTING_QUESTIONS_DB}}`)
3. Call an AI API (Anthropic Claude recommended) with the filled prompt
4. Parse and validate the returned JSON against the `mock_exam_batch` schema
5. Persist new questions to the database to prevent future duplicates

## DIY Mode (no API cost)

Run `python generate.py --diy [--port N]` to generate without the paid API:
1. A local Flask page opens in the browser.
2. Copy the shown prompt into any free AI chatbot.
3. Paste the chatbot's JSON response back; it is strictly validated.
4. Each accepted batch of 10 is saved to the DB immediately and its scenarios
   feed the next batch's dedup context. Final combined JSON lands in `jsons/`.

DIY mode requires only `BATCH_SIZE` (no `GEMINI_API_KEY`/`GEMINI_MODEL`).

## JSON Output Schema

```json
{
  "mock_exam_batch": [
    {
      "question_id": "8-char alphanumeric",
      "competency_reference": "e.g. 'Core Competency 7: Evokes Awareness'",
      "scenario_question": "3-5 sentence scenario + question prompt",
      "options": [
        { "id": "A", "text": "...", "is_correct": false },
        { "id": "B", "text": "...", "is_correct": true },
        { "id": "C", "text": "...", "is_correct": false },
        { "id": "D", "text": "...", "is_correct": false }
      ],
      "ai_rationale": { "explanation": "..." }
    }
  ]
}
```

Exactly one option per question has `is_correct: true`. No "All/None of the above".

## Question Mix Requirement

Per the prompt's execution instructions, each batch must contain:
- ~30% Ethics questions (Code of Ethics Sections 1–5)
- ~30% Boundary questions (Coaching vs. Therapy vs. Consulting)
- ~40% Core Competency questions (Listening, Questioning, Agreements, etc.)
