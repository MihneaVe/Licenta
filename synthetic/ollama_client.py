"""Thin Ollama HTTP client for the synthetic generator.

Dependency-light (just `requests`). Reads the host from $OLLAMA_HOST.
"""

import json
import os

import requests


class OllamaClient:
    def __init__(self, host: str | None = None, timeout: int = 180, think: bool = False):
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout
        # Reasoning models (e.g. Qwen3) otherwise spend the whole token budget in
        # a separate "thinking" field and return an empty "response". Disabling
        # thinking makes them answer directly; harmlessly ignored by plain models.
        self.think = think

    # -- availability ------------------------------------------------------
    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=10)
            r.raise_for_status()
            return [m.get("name", "") for m in r.json().get("models", [])]
        except Exception:
            return []

    def is_available(self, model: str) -> bool:
        models = self.list_models()
        if not models:
            return False
        if model in models:
            return True
        # Accept a base-name match (e.g. 'qwen2.5:14b' vs a differently-tagged pull).
        base = model.split(":")[0]
        return any(m.split(":")[0] == base for m in models)

    # -- generation --------------------------------------------------------
    def generate_text(self, model: str, prompt: str, *, system: str | None = None,
                      temperature: float = 0.8, num_predict: int = 400,
                      seed: int | None = None, fmt: str | None = None) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": self.think,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        if system:
            payload["system"] = system
        if fmt:
            payload["format"] = fmt
        if seed is not None:
            payload["options"]["seed"] = seed
        r = requests.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("response", "") or ""

    def generate_json(self, model: str, prompt: str, *, system: str | None = None,
                      temperature: float = 0.3, num_predict: int = 400,
                      seed: int | None = None) -> dict:
        raw = self.generate_text(model, prompt, system=system, temperature=temperature,
                                 num_predict=num_predict, seed=seed, fmt="json")
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}
