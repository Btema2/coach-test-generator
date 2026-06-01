import json
import logging
import time
from typing import Any, Callable

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (60, 300)

_RESPONSE_SCHEMA = genai.types.Schema(
    type=genai.types.Type.OBJECT,
    required=["mock_exam_batch"],
    properties={
        "mock_exam_batch": genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=[
                    "question_id",
                    "competency_reference",
                    "scenario_question",
                    "options",
                    "ai_rationale",
                ],
                properties={
                    "question_id": genai.types.Schema(type=genai.types.Type.STRING),
                    "competency_reference": genai.types.Schema(type=genai.types.Type.STRING),
                    "scenario_question": genai.types.Schema(type=genai.types.Type.STRING),
                    "options": genai.types.Schema(
                        type=genai.types.Type.ARRAY,
                        items=genai.types.Schema(
                            type=genai.types.Type.OBJECT,
                            required=["id", "text", "is_correct"],
                            properties={
                                "id": genai.types.Schema(type=genai.types.Type.STRING),
                                "text": genai.types.Schema(type=genai.types.Type.STRING),
                                "is_correct": genai.types.Schema(type=genai.types.Type.BOOLEAN),
                            },
                        ),
                    ),
                    "ai_rationale": genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        required=["explanation"],
                        properties={
                            "explanation": genai.types.Schema(type=genai.types.Type.STRING),
                        },
                    ),
                },
            ),
        ),
    },
)


def _call_with_503_retry(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        try:
            return fn(*args, **kwargs)
        except genai_errors.ServerError as exc:
            if exc.code != 503:
                raise
            logger.warning("Gemini 503 error. Attempt %d. Waiting %ds...", attempt, delay)
            time.sleep(delay)
    return fn(*args, **kwargs)


def generate_questions(prompt: str, api_key: str, model: str) -> dict:
    client = genai.Client(api_key=api_key)
    response = _call_with_503_retry(
        client.models.generate_content,
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=0.5,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
        ),
    )
    if not response.text:
        raise ValueError("Empty response from Gemini (may indicate a safety filter block)")
    try:
        return json.loads(response.text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned non-JSON: {response.text!r}") from exc
