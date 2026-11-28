---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Audit `biased_draft.json` to eliminate psychometric tells (length skew, comma/clause bias, giveaway adverbs/buzzwords, cartoonish distractors) while preserving each item's `question_id`, `competency_reference`, and `is_correct` answer key, and upgrading `ai_rationale.explanation` to cover all 4 options. Save the cleaned JSON to `audited_batch.json`.

Input files: biased_draft.json
