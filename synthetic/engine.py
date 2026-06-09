"""Agentic synthetic-post engine: draft -> critique -> (revise) -> accept.

Each :class:`PostSpec` is turned into authentic post text by an LLM, then an
LLM critic scores authenticity 1-5. If the score is below ``min_authenticity``
and revisions remain, the post is rewritten against the critique. A post is
``accepted`` once it meets the authenticity bar.

Generation is seeded per-spec (from ``spec.seed``) so a fixed RNG seed makes the
whole run reproducible.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

from . import streets as streetlib
from .taxonomy import PostSpec

# How each platform should read, so drafts feel native to the source.
PLATFORM_STYLE = {
    "reddit": ("a Reddit post in r/bucharest style: a short title-like first line, then 2-4 "
               "sentences, casual and specific, occasionally an 'Edit:' aside"),
    "x": ("a tweet (X/Twitter): under ~280 characters, punchy, 1-3 hashtags, may @mention a "
          "local authority like @Primaria_Buc"),
    "instagram": ("an Instagram caption: a few short lines, one or two emojis, 2-4 hashtags"),
    "facebook": ("a Facebook post in a local neighbourhood group: conversational, a little longer, "
                 "often addressed to neighbours"),
}

_DRAFT_SYS = ("You write realistic {lang} social-media posts as ordinary Bucharest residents "
              "reacting to everyday civic issues. You imitate real platform voice — imperfect, "
              "specific, human. Output ONLY a single JSON object, no preamble.")

_DRAFT_PROMPT = (
    "Write {style} from a resident of the {district} area of Bucharest.\n"
    "Civic topic: {subtopic} (category: {app_topic}).\n"
    "Sentiment: {sentiment}. Tone / angle: {angle}.\n"
    "Be concrete — name the place and a specific detail. Sound like a real person, not a press "
    "release. Language: {lang}.\n"
    "{street_rule}"
    'Return JSON only: {{"text": "<the post>", "author": "<a plausible handle/display name>", '
    '"hashtags": ["tag", "tag"]}}'
)

# Injected into the draft when we have real streets for the quarter.
_STREET_RULE = (
    "STREET RULE: if you mention a specific street, you MUST use this exact real street in "
    "{district}: \"{street}\". Do NOT invent or use any other street name; if a street doesn't "
    "fit naturally, don't name one. (Other real streets here include: {examples}.)\n"
)
_STREET_RULE_NONE = (
    "STREET RULE: do NOT name any specific street — keep the location to the {district} "
    "neighbourhood in general.\n"
)

_STREET_FIX_PROMPT = (
    "This {platform} post names a street that does NOT exist in {district}: {bad}.\n"
    "Rewrite it to use exactly this real street instead: \"{street}\" (or remove the street "
    "mention entirely). Keep everything else — topic, {sentiment} sentiment, tone. Language: {lang}.\n\n"
    "Post:\n{text}\n\n"
    'Return JSON only: {{"text": "<rewritten>", "author": "<handle>", "hashtags": ["tag"]}}'
)

_CRITIQUE_PROMPT = (
    "Rate how authentic and human this {platform} post sounds, 1-5 "
    "(1 = obviously AI / generic, 5 = indistinguishable from a real resident). "
    "Judge specificity, tone, and platform fit.\n\n"
    "Post:\n{text}\n\n"
    'Return JSON only: {{"authenticity": <integer 1-5>, "critique": "<one short line on what to fix>"}}'
)

_REVISE_PROMPT = (
    "Rewrite this {style} to feel more authentic, fixing this issue: {critique}\n"
    "Keep the same place, topic, and {sentiment} sentiment. Language: {lang}.\n\n"
    "Current post:\n{text}\n\n"
    'Return JSON only: {{"text": "<rewritten post>", "author": "<handle>", "hashtags": ["tag"]}}'
)


@dataclass
class PostResult:
    spec: PostSpec
    text: str = ""
    author: str = ""
    hashtags: list = field(default_factory=list)
    authenticity: int = 0
    accepted: bool = False
    revisions: int = 0
    critique: str = ""
    street: str = ""          # the real street injected/verified (if any)
    street_fixed: bool = False  # True if a hallucinated street had to be corrected
    error: str | None = None

    def to_record(self) -> dict:
        sid = hashlib.sha1(f"{self.spec.source}|{self.text}".encode("utf-8")).hexdigest()[:16]
        return {
            "id": f"syn_{sid}",
            "source": self.spec.source,
            "text": self.text,
            "author": self.author,
            "district": self.spec.district_name,
            "app_topic": self.spec.app_topic,
            "sentiment": self.spec.sentiment,
            "subtopic": self.spec.subtopic,
            "angle": self.spec.angle,
            "authenticity": self.authenticity,
            "accepted": self.accepted,
            "hashtags": self.hashtags,
            "street": self.street,
            "street_fixed": self.street_fixed,
        }


class SyntheticEngine:
    def __init__(self, client, model, *, max_revisions: int = 1,
                 min_authenticity: int = 3, language: str = "English",
                 street_max_fix: int = 2):
        self.client = client
        self.model = model
        self.max_revisions = max(0, int(max_revisions))
        self.min_authenticity = int(min_authenticity)
        self.language = language
        self.street_max_fix = max(0, int(street_max_fix))

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _style(spec: PostSpec) -> str:
        return PLATFORM_STYLE.get(spec.source, PLATFORM_STYLE["x"])

    @staticmethod
    def _coerce(out: dict):
        text = (out.get("text") or "").strip()
        author = (out.get("author") or "").strip()[:255]
        tags = out.get("hashtags") or []
        if isinstance(tags, str):
            tags = [tags]
        tags = [str(t).lstrip("#").strip() for t in tags if str(t).strip()][:6]
        return text, author, tags

    def _street_rule(self, spec: PostSpec, chosen: str | None) -> str:
        district = spec.district_name or "Bucharest"
        if chosen:
            examples = ", ".join((spec.streets or {}).get("major", [])[:5]) or chosen
            return _STREET_RULE.format(district=district, street=chosen, examples=examples)
        if spec.streets:  # we have a list but picked none → still forbid inventing
            return _STREET_RULE_NONE.format(district=district)
        return ""  # no geo info for this quarter: leave street handling to the model

    def _draft(self, spec: PostSpec, chosen: str | None):
        prompt = _DRAFT_PROMPT.format(
            style=self._style(spec), district=spec.district_name or "Bucharest",
            subtopic=spec.subtopic, app_topic=spec.app_topic,
            sentiment=spec.sentiment, angle=spec.angle, lang=self.language,
            street_rule=self._street_rule(spec, chosen),
        )
        out = self.client.generate_json(
            self.model, prompt, system=_DRAFT_SYS.format(lang=self.language),
            temperature=0.9, num_predict=420, seed=spec.seed,
        )
        return self._coerce(out)

    def _critique(self, spec: PostSpec, text: str):
        prompt = _CRITIQUE_PROMPT.format(platform=spec.source, text=text)
        out = self.client.generate_json(
            self.model, prompt, temperature=0.0, num_predict=80, seed=spec.seed + 1,
        )
        try:
            score = int(out.get("authenticity"))
        except (TypeError, ValueError):
            score = self.min_authenticity  # don't block on an unparseable critique
        score = max(1, min(5, score))
        return score, str(out.get("critique") or "").strip()

    def _revise(self, spec: PostSpec, text: str, critique: str, attempt: int):
        prompt = _REVISE_PROMPT.format(
            style=self._style(spec), critique=critique or "make it more specific and human",
            sentiment=spec.sentiment, lang=self.language, text=text,
        )
        out = self.client.generate_json(
            self.model, prompt, temperature=0.85, num_predict=420, seed=spec.seed + 10 + attempt,
        )
        return self._coerce(out)

    def _verify_streets(self, spec: PostSpec, text: str, author: str, tags: list,
                        chosen: str | None):
        """Bounded verifier loop: ensure any street the post names really exists
        in this quarter. Re-prompts the model to fix hallucinations, then falls
        back to a deterministic replacement. Returns (text, author, tags, fixed)."""
        if not spec.streets:
            return text, author, tags, False

        fixed = False
        for attempt in range(self.street_max_fix):
            bad = streetlib.validate(text, spec.streets)
            if not bad:
                break
            fixed = True
            target = chosen or streetlib.pick_street(spec.streets, random.Random(spec.seed + 99))
            out = self.client.generate_json(
                self.model,
                _STREET_FIX_PROMPT.format(
                    platform=spec.source, district=spec.district_name or "Bucharest",
                    bad="; ".join(bad), street=target or "(none)",
                    sentiment=spec.sentiment, lang=self.language, text=text,
                ),
                temperature=0.4, num_predict=420, seed=spec.seed + 50 + attempt,
            )
            rtext, rauthor, rtags = self._coerce(out)
            if rtext:
                text, author, tags = rtext, rauthor or author, rtags or tags

        # Deterministic safety net — guarantees no invented street survives.
        bad = streetlib.validate(text, spec.streets)
        if bad:
            fixed = True
            text = streetlib.enforce(text, bad, chosen or streetlib.pick_street(
                spec.streets, random.Random(spec.seed + 7)))
        return text, author, tags, fixed

    # -- public ------------------------------------------------------------
    def generate_one(self, spec: PostSpec) -> PostResult:
        try:
            # Pick a real street up front (boulevard-preferred) to steer the draft.
            chosen = streetlib.pick_street(spec.streets, random.Random(spec.seed)) if spec.streets else None

            text, author, tags = self._draft(spec, chosen)
            if not text:
                return PostResult(spec=spec, error="empty draft")

            authenticity, critique = self._critique(spec, text)
            revisions = 0
            while authenticity < self.min_authenticity and revisions < self.max_revisions:
                revisions += 1
                rtext, rauthor, rtags = self._revise(spec, text, critique, revisions)
                if rtext:
                    text, author, tags = rtext, rauthor or author, rtags or tags
                authenticity, critique = self._critique(spec, text)

            # Verifier loop: keep street references factual for this quarter.
            text, author, tags, street_fixed = self._verify_streets(spec, text, author, tags, chosen)

            return PostResult(
                spec=spec, text=text, author=author, hashtags=tags,
                authenticity=authenticity, accepted=authenticity >= self.min_authenticity,
                revisions=revisions, critique=critique,
                street=chosen or "", street_fixed=street_fixed,
            )
        except Exception as exc:  # noqa: BLE001 — surface as a per-post error, keep the run going
            return PostResult(spec=spec, error=str(exc))
