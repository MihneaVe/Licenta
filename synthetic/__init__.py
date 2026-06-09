"""Synthetic civic-post generator (reconstructed).

A small, framework-agnostic package that produces platform-authentic Bucharest
civic posts via an agentic draft -> critique -> revise loop over a local Ollama
model. Used by ../_gen_demo.py to seed demo data into Supabase.

Public API (the contract _gen_demo.py depends on):
    ollama_client.OllamaClient            — .is_available(model), .list_models(), .generate*/
    taxonomy.sample_specs(...)            — build a list[PostSpec]
    engine.SyntheticEngine(...)           — .generate_one(spec) -> PostResult
    engine.PostResult                     — .error, .accepted, .spec, .to_record()
"""

from .taxonomy import PostSpec, sample_specs, APP_TOPICS
from .engine import SyntheticEngine, PostResult
from .ollama_client import OllamaClient

__all__ = [
    "PostSpec", "sample_specs", "APP_TOPICS",
    "SyntheticEngine", "PostResult", "OllamaClient",
]
