from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class OllamaConfig:
    """
    Minimal Ollama client config.

    - base_url: Ollama server URL. Default is the local Ollama API.
    - model: model name (left as a configurable blank).
    """

    base_url: str = "http://localhost:11434"
    model: str = ""  # e.g. "qwen2.5:7b-instruct", "llama3.1:8b-instruct"
    timeout_s: int = 120


class OllamaLLM:
    def __init__(self, cfg: OllamaConfig):
        if not cfg.model:
            raise ValueError(
                "OllamaConfig.model is empty. Please pass --ollama_model <model_name>."
            )
        self.cfg = cfg

    def generate(self, prompt: str, temperature: float = 0.2, max_tokens: int = 1024) -> str:
        """
        Use Ollama's /api/generate endpoint.
        We intentionally keep this minimal and dependency-free.
        """
        url = f"{self.cfg.base_url.rstrip('/')}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.cfg.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                # Ollama uses num_predict; keep a sane fallback if ignored by some backends.
                "num_predict": max_tokens,
            },
        }
        r = requests.post(url, json=payload, timeout=self.cfg.timeout_s)
        r.raise_for_status()
        data = r.json()
        if "response" not in data:
            raise RuntimeError(f"Unexpected Ollama response: {json.dumps(data)[:500]}")
        return str(data["response"]).strip()

