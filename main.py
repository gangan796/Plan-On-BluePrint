from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple

# Allow running as a script from repo root:
# `python PoBL/main.py ...` should import local modules.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from llm_ollama import OllamaConfig, OllamaLLM
from prompts import (
    ENTITY_PRUNE_PROMPT,
    REASONING_PROMPT,
    RELATION_SELECT_PROMPT,
    SUBOBJECTIVE_PROMPT,
)
from utils import format_triples_for_prompt, safe_parse_json, safe_parse_python_list
from wikidata import WikidataClient, WikidataConfig


@dataclass
class RunConfig:
    depth: int = 2
    temperature_explore: float = 0.2
    temperature_reason: float = 0.2
    max_tokens: int = 1024
    lang: str = "en"


def pick_topic_entity(wd: WikidataClient, question: str, lang: str) -> Tuple[str, str] | None:
    """
    Minimal "entity linking": use the first exact-label match for any quoted phrase,
    otherwise try the whole question as a label (often empty).
    For a real system you would replace this with NER + entity linking.
    """
    # naive: try a couple of common entity candidates by splitting
    # In practice, pass --topic "Entity Label" to avoid this.
    candidates = []
    for token in question.replace("?", " ").replace(".", " ").split():
        if len(token) >= 4:
            candidates.append(token)

    # try the longest tokens first
    candidates = sorted(set(candidates), key=len, reverse=True)[:8]
    for c in candidates:
        hits = wd.search_entity(c, limit=1, lang=lang)
        if hits:
            return hits[0]
    return None


def run_min_pog(question: str, llm: OllamaLLM, wd: WikidataClient, cfg: RunConfig, topic_label: str | None):
    # 1) subobjectives
    sub_prompt = SUBOBJECTIVE_PROMPT.format(question=question)
    sub_raw = llm.generate(sub_prompt, temperature=cfg.temperature_reason, max_tokens=cfg.max_tokens)
    subobjectives = safe_parse_python_list(sub_raw)

    # 2) topic entity (either user-provided label or naive linker)
    if topic_label:
        hits = wd.search_entity(topic_label, limit=1, lang=cfg.lang)
        if not hits:
            raise RuntimeError(f"No Wikidata entity found for topic label: {topic_label}")
        topic_qid, topic_name = hits[0]
    else:
        picked = pick_topic_entity(wd, question, cfg.lang)
        if not picked:
            # fallback: no graph exploration
            knowledge = ""
            reason_raw = llm.generate(
                REASONING_PROMPT.format(question=question, knowledge=knowledge),
                temperature=cfg.temperature_reason,
                max_tokens=cfg.max_tokens,
            )
            return {"subobjectives": subobjectives, "topic_entity": None, "knowledge": [], "llm": reason_raw}
        topic_qid, topic_name = picked

    knowledge_triples: List[tuple] = []
    frontier: List[Tuple[str, str]] = [(topic_qid, topic_name)]

    # 3) iterative graph exploration (very small)
    for _depth in range(1, cfg.depth + 1):
        if not frontier:
            break

        # Enumerate predicates around the *first* frontier node (minimal)
        cur_qid, cur_label = frontier[0]
        preds = wd.list_predicates_around_entity(cur_qid, limit=80)
        preds_preview = preds[:80]

        rel_prompt = RELATION_SELECT_PROMPT.format(
            question=question,
            subobjectives=subobjectives,
            topic_entity_label=cur_label,
            topic_entity_id=cur_qid,
            predicates=preds_preview,
        )
        rel_raw = llm.generate(rel_prompt, temperature=cfg.temperature_explore, max_tokens=cfg.max_tokens)
        selected_preds = [p for p in safe_parse_python_list(rel_raw) if isinstance(p, str) and p.startswith("wdt:P")]
        selected_preds = selected_preds[:3]  # keep minimal

        expanded: List[tuple] = []
        for p in selected_preds:
            expanded += wd.expand_triples(cur_qid, p, direction="out", limit=20, lang=cfg.lang)

        if not expanded:
            break

        # 4) prune entities (minimal: prune based on triples text)
        prune_prompt = ENTITY_PRUNE_PROMPT.format(
            question=question,
            triples=format_triples_for_prompt(expanded),
        )
        pr_raw = llm.generate(prune_prompt, temperature=cfg.temperature_reason, max_tokens=cfg.max_tokens)
        keep_labels = set(x for x in safe_parse_python_list(pr_raw) if isinstance(x, str))

        pruned = [t for t in expanded if (len(t) >= 4 and str(t[3]) in keep_labels) or not keep_labels]
        pruned = pruned[:25]
        knowledge_triples.extend(pruned)

        # update frontier (very small: labels only; no QID recovery here)
        # In a full system, we'd carry QIDs for objects and expand multi-hop.
        frontier = []

    # 5) final reasoning
    knowledge_text = format_triples_for_prompt(knowledge_triples)
    reason_prompt = REASONING_PROMPT.format(question=question, knowledge=knowledge_text)
    reason_raw = llm.generate(reason_prompt, temperature=cfg.temperature_reason, max_tokens=cfg.max_tokens)

    return {
        "subobjectives": subobjectives,
        "topic_entity": {"qid": topic_qid, "label": topic_name},
        "knowledge": knowledge_triples,
        "llm": reason_raw,
        "parsed": _try_parse_json(reason_raw),
    }


def _try_parse_json(text: str):
    try:
        return safe_parse_json(text)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="PoBL: minimal PoG-like flow using Ollama + Wikidata SPARQL.")
    ap.add_argument("--question", type=str, required=True, help="Question text.")
    ap.add_argument("--topic", type=str, default="", help="Optional topic entity label (recommended).")
    ap.add_argument("--depth", type=int, default=2, help="Exploration depth (minimal framework; default 2).")
    ap.add_argument("--lang", type=str, default="en", help="Wikidata label language, e.g. en/zh.")

    ap.add_argument("--ollama_base_url", type=str, default="http://localhost:11434", help="Ollama server base URL.")
    ap.add_argument("--ollama_model", type=str, default="", help="Ollama model name (left configurable).")
    ap.add_argument("--temperature_explore", type=float, default=0.2)
    ap.add_argument("--temperature_reason", type=float, default=0.2)
    ap.add_argument("--max_tokens", type=int, default=1024)

    args = ap.parse_args()

    llm = OllamaLLM(OllamaConfig(base_url=args.ollama_base_url, model=args.ollama_model))
    wd = WikidataClient(WikidataConfig())
    cfg = RunConfig(
        depth=args.depth,
        temperature_explore=args.temperature_explore,
        temperature_reason=args.temperature_reason,
        max_tokens=args.max_tokens,
        lang=args.lang,
    )

    result = run_min_pog(args.question, llm, wd, cfg, topic_label=(args.topic or None))
    # print as a readable JSON-ish block
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

