"""LLM-powered structured extraction for already-ingested social posts.

When the deterministic parsers in ``apps.ingestion.parsers`` fail to
cleanly separate metadata from body — typically because the user pasted
a messy Reddit/X selection — this module asks a local Ollama model
(default: ``qwen2.5:7b``) to re-extract the fields and emit JSON
matching the :class:`~apps.analytics.models.SocialPost` schema.

The model is also asked to *generate* a short title when one is not
already present (X posts almost never have one).

Stays local — no calls leave the machine. Uses Ollama's ``format: "json"``
mode so the response is guaranteed parseable JSON.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

import requests


logger = logging.getLogger(__name__)


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
LLM_EXTRACTOR_MODEL = os.environ.get("LLM_EXTRACTOR_MODEL", "qwen2.5:7b")


SECTOR_RE = re.compile(r"sector(?:ul)?\s*([1-6])\b", flags=re.IGNORECASE)


@dataclass
class ExtractedFields:
    """Structured output of one LLM extraction call.

    All fields are optional except ``body``; the caller decides which
    ones override the existing :class:`SocialPost` row.
    """

    title: str = ""
    body: str = ""
    author: str = ""
    date_iso: Optional[str] = None  # ISO 8601 if the LLM could resolve one
    mentioned_sector: Optional[int] = None  # 1..6 for "Sector 3" mentions
    location_hint: str = ""  # free-form place name (street, neighborhood)
    title_was_generated: bool = False
    raw_response: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class LLMExtractor:
    """Re-extract structured fields from messy paste content using Ollama."""

    DEFAULT_TIMEOUT = 120  # seconds — qwen2.5:7b on CPU can take a while

    def __init__(
        self,
        model: str = LLM_EXTRACTOR_MODEL,
        host: str = OLLAMA_HOST,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.model = model
        self.host = host
        self.timeout = timeout
        self.api_url = f"{self.host}/api/generate"

    # ------------------------------------------------------------------ availability

    def is_available(self) -> bool:
        """Check Ollama is reachable and our model is pulled."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            return any(self.model in name for name in models)
        except Exception as exc:
            logger.warning("Ollama availability probe failed: %s", exc)
            return False

    # ------------------------------------------------------------------ extraction

    def extract(
        self,
        raw_content: str,
        source: str,
        existing_title: str = "",
    ) -> ExtractedFields:
        """Ask the model to split ``raw_content`` into structured fields.

        Args:
            raw_content: Whatever messy text the user pasted (may already
                have been lightly normalized by the deterministic parser).
            source: ``"reddit"`` or ``"x"`` — used to tailor the prompt
                with platform-specific hints.
            existing_title: A title we already trust (e.g. from a clean
                JSON paste). When non-empty the model will *not*
                regenerate one.

        Returns:
            :class:`ExtractedFields` with normalized values; on failure
            returns a degenerate object whose ``body`` falls back to the
            original input.
        """
        if not raw_content or not raw_content.strip():
            return ExtractedFields(body="", raw_response="")

        prompt = self._build_prompt(raw_content, source, existing_title)
        raw = self._call_json(prompt)

        if not raw:
            # Couldn't reach the model — keep the original content untouched.
            return ExtractedFields(body=raw_content, raw_response="")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON: %s", raw[:200])
            return ExtractedFields(body=raw_content, raw_response=raw)

        fields = self._normalize(data, raw_content, existing_title)
        fields.raw_response = raw
        return fields

    def generate_title(self, body: str, max_words: int = 10) -> str:
        """Generate a concise headline-style title for a post body.

        Used when ``extract()`` couldn't recover a title from the source
        and there isn't one to fall back on.
        """
        body = (body or "").strip()
        if not body:
            return ""

        prompt = (
            "Generează un titlu scurt (maxim "
            f"{max_words} cuvinte) pentru următoarea postare civică din "
            "București. Răspunde DOAR cu titlul, fără ghilimele, fără "
            "punctuație finală, fără explicații.\n\n"
            f"Postare:\n{body[:1500]}\n\n"
            "Titlu:"
        )
        raw = self._call_text(prompt, max_tokens=40)
        return self._clean_title(raw, max_words)

    # ------------------------------------------------------------------ prompt + calls

    def _build_prompt(self, raw_content: str, source: str, existing_title: str) -> str:
        source_hint = {
            "reddit": (
                "Sursa este Reddit (subreddit r/bucuresti). Pasta poate "
                "conține: linia 'Go to bucuresti', timpul ('• 15h ago'), "
                "username-ul autorului (un singur cuvânt fără spații), "
                "titlul postării, eticheta de flair (Discutie, Sport, "
                "Infrastructura, Societate, etc.), apoi corpul postării, "
                "iar la final numere de comentarii / voturi."
            ),
            "x": (
                "Sursa este X (Twitter). Pasta poate conține: numele "
                "afișat, @handle, data ('18 mar.', '7 apr.'), corpul "
                "tweet-ului, link-uri trunchiate, hashtag-uri amestecate "
                "în text, și metrici (Replies, Reposts, Likes, Views)."
            ),
        }.get(source, "")

        title_directive = (
            f'Folosește exact acest titlu: "{existing_title}". Nu îl modifica.'
            if existing_title
            else (
                "Dacă există un titlu evident în text, extrage-l. Altfel "
                "lasă câmpul `title` ca string gol — îl vom genera ulterior."
            )
        )

        return (
            "Ești un parser care extrage metadate dintr-o postare de pe rețele "
            "sociale și răspunde STRICT cu un obiect JSON valid.\n\n"
            f"{source_hint}\n\n"
            "Returnează un obiect JSON cu EXACT aceste chei:\n"
            '  "title": string (titlul postării, sau "" dacă nu există)\n'
            '  "body": string (textul curat al postării — fără autor, fără data, '
            'fără metrici, fără hashtag-uri lipite la final, fără URL-uri)\n'
            '  "author": string (username-ul autorului, fără @ sau u/, sau "")\n'
            '  "date_iso": string (data postării în format ISO 8601 dacă apare, '
            'sau null. Dacă vezi ceva de tipul "15h ago" sau "18 mar.", '
            "lasă null — nu inventa o dată.)\n"
            '  "mentioned_sector": integer 1-6 (numărul sectorului '
            "Bucureștiului menționat în text, sau null)\n"
            '  "location_hint": string (numele unei străzi, cartier sau '
            'punct de reper, sau "")\n\n'
            f"{title_directive}\n\n"
            "Păstrează diacriticele românești. Nu adăuga câmpuri extra. "
            "Nu pune comentarii. Nu folosi markdown. Nu pune ghilimele "
            "în jurul JSON-ului.\n\n"
            "TEXT DE PROCESAT:\n"
            "---\n"
            f"{raw_content[:4000]}\n"
            "---\n\n"
            "JSON:"
        )

    def _call_json(self, prompt: str, max_tokens: int = 600) -> str:
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.1,
                    },
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama at %s.", self.host)
            return ""
        except Exception as exc:
            logger.error("Ollama JSON call failed: %s", exc)
            return ""

    def _call_text(self, prompt: str, max_tokens: int = 60) -> str:
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.4,
                    },
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except Exception as exc:
            logger.error("Ollama text call failed: %s", exc)
            return ""

    # ------------------------------------------------------------------ post-processing

    def _normalize(
        self,
        data: dict,
        raw_content: str,
        existing_title: str,
    ) -> ExtractedFields:
        body = (data.get("body") or "").strip()
        if not body:
            body = raw_content.strip()

        title = (data.get("title") or "").strip()
        if existing_title:
            title = existing_title

        author = self._strip_handle_prefix((data.get("author") or "").strip())

        date_iso = data.get("date_iso") or None
        if date_iso and not self._looks_like_iso(date_iso):
            date_iso = None

        # Trust the deterministic regex first — it only matches literal
        # "Sectorul N" / "Sector N" strings and won't hallucinate from
        # neighborhood names the way the LLM sometimes does.
        sector = self._fallback_sector(raw_content)
        if sector is None:
            llm_sector = data.get("mentioned_sector")
            if isinstance(llm_sector, int) and 1 <= llm_sector <= 6:
                sector = llm_sector

        return ExtractedFields(
            title=title,
            body=body,
            author=author,
            date_iso=date_iso,
            mentioned_sector=sector,
            location_hint=(data.get("location_hint") or "").strip(),
        )

    @staticmethod
    def _strip_handle_prefix(value: str) -> str:
        return value.lstrip("@").lstrip("u/").lstrip("/u/").strip()

    @staticmethod
    def _looks_like_iso(value: str) -> bool:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _fallback_sector(text: str) -> Optional[int]:
        m = SECTOR_RE.search(text)
        if m:
            try:
                return int(m.group(1))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _clean_title(raw: str, max_words: int) -> str:
        if not raw:
            return ""
        # Take only the first non-empty line and strip surrounding noise.
        first = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
        first = first.strip("\"'`*_ ")
        # Drop a leading "Titlu:" / "Title:" the model sometimes echoes.
        first = re.sub(r"^(titlu|title)\s*:\s*", "", first, flags=re.IGNORECASE)
        words = first.split()
        if len(words) > max_words:
            first = " ".join(words[:max_words])
        return first.rstrip(".!?,:;").strip()
