#!/usr/bin/env python3
"""Validate ICF ACC exam JSON structure, psychometric balance, and EN/UK parity."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_CC_RE = re.compile(r"(?:Core Competency|Ключова компетенція)\s*(\d+)", re.IGNORECASE)
_ETHICS_RE = re.compile(r"ethic|етичн", re.IGNORECASE)
_BANNED_PHRASES = (
    "all of the above",
    "none of the above",
    "усе вищезазначене",
    "все вищезазначене",
    "жодне з переліченого",
    "жоден із перелічених",
)
_GIVEAWAY_ADVERBS = (
    "immediately",
    "completely",
    "firmly",
    "quietly",
    "secretly",
    "outright",
    "never",
    "automatically",
    "without judgment",
    "негайно",
    "цілковито",
    "категорично",
    "нишком",
    "таємно",
    "ніколи",
    "автоматично",
    "без осуду",
)


def area_key(ref: str) -> str:
    """Mirror serve._area grouping key."""
    m = _CC_RE.search(ref)
    if m:
        return f"cc{int(m.group(1))}"
    if _ETHICS_RE.search(ref):
        return "ethics"
    return "other"


def validate_exam(path: Path, allow_partial: bool = False) -> tuple[list[str], list[str], dict]:
    """Return (errors, warnings, summary) for a single exam JSON file."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: invalid JSON ({exc})"], warnings, {}

    if not isinstance(data, dict) or not isinstance(data.get("mock_exam_batch"), list):
        return [f"{path}: missing top-level 'mock_exam_batch' array"], warnings, {}

    questions = data["mock_exam_batch"]
    if not questions:
        return [f"{path}: 'mock_exam_batch' is empty"], warnings, {}
    if not allow_partial and len(questions) != 60:
        errors.append(f"{path}: expected 60 questions, got {len(questions)} (pass --allow-partial for drafts)")

    seen_ids: set[str] = set()
    seen_stems: set[str] = set()
    keys = Counter()
    areas = Counter()
    stem_words: list[int] = []
    max_spread = 0
    key_adverb_hits = 0
    distractor_adverb_hits = 0
    key_commas = 0
    distractor_commas = 0

    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            errors.append(f"Item #{idx}: must be an object")
            continue
        qid = str(q.get("question_id", ""))
        if not qid:
            errors.append(f"Item #{idx}: missing question_id")
        elif qid in seen_ids:
            errors.append(f"Q{qid}: duplicate question_id")
        seen_ids.add(qid)

        ref = q.get("competency_reference", "")
        stem = q.get("scenario_question", "")
        if not ref or not isinstance(ref, str):
            errors.append(f"Q{qid or idx}: missing competency_reference")
        else:
            ak = area_key(ref)
            if ak == "other":
                errors.append(f"Q{qid or idx}: unmapped competency_reference '{ref}'")
            areas[ak] += 1

        if not stem or not isinstance(stem, str):
            errors.append(f"Q{qid or idx}: missing scenario_question")
        else:
            norm = stem.strip().lower()
            if norm in seen_stems:
                errors.append(f"Q{qid or idx}: duplicate scenario_question")
            seen_stems.add(norm)
            sw = len(stem.split())
            stem_words.append(sw)
            if sw > 38:
                warnings.append(f"Q{qid or idx}: long stem ({sw} words; target <= 30 before/with prompt)")

        rationale = (q.get("ai_rationale") or {}).get("explanation", "")
        if not rationale or not isinstance(rationale, str):
            errors.append(f"Q{qid or idx}: missing ai_rationale.explanation")

        opts = q.get("options")
        if not isinstance(opts, list) or [o.get("id") for o in opts if isinstance(o, dict)] != ["A", "B", "C", "D"]:
            errors.append(f"Q{qid or idx}: options must be A, B, C, D")
            continue

        correct_opts = [o for o in opts if o.get("is_correct") is True]
        if len(correct_opts) != 1:
            errors.append(f"Q{qid or idx}: expected exactly 1 is_correct=true, got {len(correct_opts)}")
            continue

        keys[correct_opts[0]["id"]] += 1
        olens: list[int] = []
        for o in opts:
            text = str(o.get("text", "")).strip()
            if not text:
                errors.append(f"Q{qid or idx} option {o.get('id')}: empty text")
                continue
            low = text.lower()
            for banned in _BANNED_PHRASES:
                if banned in low:
                    errors.append(f"Q{qid or idx} option {o.get('id')}: contains banned phrase '{banned}'")
            olens.append(len(text.split()))
            adv = sum(1 for w in _GIVEAWAY_ADVERBS if w in low)
            commas = text.count(",")
            if o.get("is_correct"):
                key_adverb_hits += adv
                key_commas += commas
            else:
                distractor_adverb_hits += adv
                distractor_commas += commas

        if len(olens) == 4:
            spread = max(olens) - min(olens)
            max_spread = max(max_spread, spread)
            if spread > 6:
                warnings.append(f"Q{qid or idx}: option word spread is {spread} ({olens})")

    if len(questions) == 60:
        if any(keys[k] != 15 for k in ("A", "B", "C", "D")):
            warnings.append(f"Answer keys not 15/15/15/15: {dict(sorted(keys.items()))}")
        if areas["ethics"] != 18 or areas["cc1"] != 18:
            warnings.append(f"Domain split differs from 18 ethics / 18 cc1 / 24 cc2-8: {dict(sorted(areas.items()))}")

    if key_adverb_hits > 0 and key_adverb_hits * 3 > distractor_adverb_hits + 2:
        warnings.append(
            f"Giveaway adverbs skewed toward keys (keys={key_adverb_hits}, distractors={distractor_adverb_hits})"
        )
    n_q = max(1, len(questions))
    if key_commas / n_q > (distractor_commas / (3 * n_q)) * 2.0 and key_commas / n_q >= 0.25:
        warnings.append(
            f"Comma complexity skewed toward keys (avg key={key_commas/n_q:.2f}, distractor={distractor_commas/(3*n_q):.2f})"
        )

    summary = {
        "count": len(questions),
        "keys": dict(sorted(keys.items())),
        "areas": dict(sorted(areas.items())),
        "stem_words_avg": round(sum(stem_words) / len(stem_words), 1) if stem_words else 0,
        "max_option_spread": max_spread,
    }
    return errors, warnings, summary


def validate_pair(en_path: Path, uk_path: Path) -> list[str]:
    """Check translation key, order, and competency_reference digit/area parity."""
    errors: list[str] = []
    en_qs = json.loads(en_path.read_text(encoding="utf-8"))["mock_exam_batch"]
    uk_qs = json.loads(uk_path.read_text(encoding="utf-8"))["mock_exam_batch"]
    if len(en_qs) != len(uk_qs):
        return [f"Pair count mismatch: {en_path.name}={len(en_qs)} vs {uk_path.name}={len(uk_qs)}"]

    for i, (e, u) in enumerate(zip(en_qs, uk_qs), start=1):
        if str(e.get("question_id")) != str(u.get("question_id")):
            errors.append(f"Index {i}: question_id mismatch ({e.get('question_id')} vs {u.get('question_id')})")
        e_flags = [o.get("is_correct") for o in e.get("options", [])]
        u_flags = [o.get("is_correct") for o in u.get("options", [])]
        if e_flags != u_flags:
            errors.append(f"Q{e.get('question_id')}: answer key mismatch between EN and UK")
        e_dig = re.search(r"\d", e.get("competency_reference", ""))
        u_dig = re.search(r"\d", u.get("competency_reference", ""))
        if not e_dig or not u_dig or e_dig.group() != u_dig.group():
            errors.append(f"Q{e.get('question_id')}: competency_reference first digit mismatch")
        if area_key(e.get("competency_reference", "")) != area_key(u.get("competency_reference", "")):
            errors.append(f"Q{e.get('question_id')}: area grouping mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ICF ACC exam JSON files.")
    parser.add_argument("exam", type=Path, help="Path to exam JSON file.")
    parser.add_argument("--pair", type=Path, help="Optional Ukrainian translation JSON to check parity.")
    parser.add_argument("--allow-partial", action="store_true", help="Allow fewer than 60 items (for drafts).")
    args = parser.parse_args()

    errors, warnings, summary = validate_exam(args.exam, allow_partial=args.allow_partial)
    print(f"[Primary] {args.exam}: {summary}")

    if args.pair:
        p_errors, p_warnings, p_summary = validate_exam(args.pair, allow_partial=args.allow_partial)
        errors.extend(p_errors)
        warnings.extend(p_warnings)
        print(f"[Pair]    {args.pair}: {p_summary}")
        if not p_errors and not errors:
            errors.extend(validate_pair(args.exam, args.pair))

    for w in warnings:
        print(f"WARN:  {w}")
    for e in errors:
        print(f"ERROR: {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
