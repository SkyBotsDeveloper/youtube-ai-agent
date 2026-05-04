from __future__ import annotations

import json
import re
from typing import Any


class ScriptParseError(ValueError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ScriptParseError("LLM returned an empty response.")

    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()

    attempts = [cleaned]
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last > first:
        attempts.append(cleaned[first : last + 1])

    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ScriptParseError("Could not parse a JSON object from the LLM response.")
