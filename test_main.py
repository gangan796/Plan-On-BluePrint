from __future__ import annotations

"""
Simple helper script to test PoBL/main.py.

Usage example (PowerShell):

    cd "e:/论文/BluePrintRAG/PoBL"
    python test_main.py ^
        --question "What is the currency used in Kenya?" ^
        --topic "Kenya" ^
        --ollama_model "<your_ollama_model_name>"

This will:
1. Call the minimal PoG pipeline defined in main.py
2. Print subobjectives, topic entity, collected triples and final answer (if parsable)
"""

import argparse
import json
import os
import sys

# Ensure we can import local main.py when running from project root or PoBL directory
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from main import RunConfig, run_min_pog  # type: ignore
from llm_ollama import OllamaConfig, OllamaLLM  # type: ignore
from wikidata import WikidataClient, WikidataConfig  # type: ignore


def main():
    parser = argparse.ArgumentParser(description="Test harness for PoBL/main.py minimal PoG pipeline.")
    parser.add_argument("--question", type=str, required=True, help="Question text to test.")
    parser.add_argument("--topic", type=str, default="", help="Optional topic entity label (recommended).")

    parser.add_argument("--ollama_base_url", type=str, default="http://localhost:11434", help="Ollama server base URL.")
    parser.add_argument("--ollama_model", type=str, required=True, help="Ollama model name to use.")

    parser.add_argument("--depth", type=int, default=2, help="Exploration depth (same meaning as main.py).")
    parser.add_argument("--lang", type=str, default="en", help="Wikidata label language.")
    parser.add_argument("--temperature_explore", type=float, default=0.2)
    parser.add_argument("--temperature_reason", type=float, default=0.2)
    parser.add_argument("--max_tokens", type=int, default=1024)

    args = parser.parse_args()

    llm = OllamaLLM(OllamaConfig(base_url=args.ollama_base_url, model=args.ollama_model))
    wd = WikidataClient(WikidataConfig())
    cfg = RunConfig(
        depth=args.depth,
        temperature_explore=args.temperature_explore,
        temperature_reason=args.temperature_reason,
        max_tokens=args.max_tokens,
        lang=args.lang,
    )

    result = run_min_pog(
        question=args.question,
        llm=llm,
        wd=wd,
        cfg=cfg,
        topic_label=(args.topic or None),
    )

    # Pretty-print a compact view
    print("==== Subobjectives ====")
    print(json.dumps(result.get("subobjectives"), ensure_ascii=False, indent=2))

    print("\n==== Topic Entity ====")
    print(json.dumps(result.get("topic_entity"), ensure_ascii=False, indent=2))

    print("\n==== Knowledge Triples (first 10) ====")
    triples = result.get("knowledge") or []
    print(json.dumps(triples[:10], ensure_ascii=False, indent=2))

    print("\n==== Raw LLM Output ====")
    print(result.get("llm"))

    print("\n==== Parsed JSON (if any) ====")
    print(json.dumps(result.get("parsed"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

