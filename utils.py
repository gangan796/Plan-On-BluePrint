from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from typing import Any, List, Sequence


def safe_parse_python_list(text: str) -> List[Any]:
    """
    Parse LLM output that should be a Python list.
    Extremely defensive; falls back to best-effort splitting.
    """
    text = text.strip()
    # keep only the last [...] block if model printed extra stuff
    l = text.rfind("[")
    r = text.rfind("]")
    if 0 <= l < r:
        text = text[l : r + 1]

    try:
        v = ast.literal_eval(text)
        if isinstance(v, list):
            return v
    except Exception:
        pass

    # fallback: try comma split inside brackets
    text = text.strip().strip("[").strip("]")
    if not text:
        return []
    parts = [p.strip().strip("'").strip('"') for p in text.split(",")]
    return [p for p in parts if p]


def safe_parse_json(text: str) -> dict:
    text = text.strip()
    l = text.find("{")
    r = text.rfind("}")
    if 0 <= l < r:
        text = text[l : r + 1]
    return json.loads(text)


def format_triples_for_prompt(triples: Sequence[tuple]) -> str:
    lines = []
    for t in triples:
        lines.append(", ".join(str(x) for x in t))
    return "\n".join(lines)

