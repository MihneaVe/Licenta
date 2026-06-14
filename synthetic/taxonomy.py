"""Spec sampling for synthetic civic posts.

A :class:`PostSpec` captures *what* a post should be about (platform, sentiment,
civic topic + concrete subtopic, rhetorical angle, and where it's set). The
engine turns a spec into authentic post text. ``_gen_demo.py`` overrides each
spec's ``district_name``/``sector`` from its coverage plan after sampling.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# The six app-level topics the dashboard knows (must match analytics_topiccategory).
APP_TOPICS = ["infrastructure", "cleanliness", "safety", "transport", "greenspace", "other"]

# Concrete civic issues per topic - gives the model something specific to write about.
SUBTOPICS = {
    "infrastructure": ["potholes", "broken sidewalks", "street lighting outages", "burst water pipes",
                       "crumbling building facades", "winter heating outages", "flooded underpasses"],
    "cleanliness": ["overflowing bins", "illegal construction dumping", "littered parks",
                    "graffiti on blocks", "missed street cleaning", "bad smells near markets"],
    "safety": ["poorly lit streets", "speeding cars near schools", "stray dog packs",
               "petty theft in the area", "broken pedestrian crossings", "vandalised playgrounds"],
    "transport": ["bus delays", "overcrowded trams", "rare metro frequency", "no parking spots",
                  "missing bike lanes", "endless traffic jams", "scrapped tram lines"],
    "greenspace": ["neglected park maintenance", "trees cut for parking", "broken playground equipment",
                   "green areas paved over", "dried-up flower beds", "no benches left"],
    "other": ["street noise at night", "slow city-hall bureaucracy", "a great local event",
              "unanswered complaints", "neighbourhood community spirit", "lack of pet facilities"],
}

# Rhetorical stance, keyed by sentiment.
ANGLES = {
    "negative": ["frustrated complaint", "calling out the authorities", "sarcastic vent",
                 "worried plea for help", "fed-up rant", "angry callout with a photo"],
    "positive": ["grateful shoutout", "celebrating a real improvement", "praising the local council",
                 "happy update for neighbours", "appreciation post", "relieved thank-you"],
    "neutral": ["matter-of-fact observation", "asking neighbours for info", "neutral status update",
                "balanced take with pros and cons", "mild suggestion", "calm heads-up"],
}

# Sentiment mix when more than one sentiment is requested.
_REALISTIC_WEIGHTS = {"negative": 0.62, "positive": 0.30, "neutral": 0.08}


@dataclass
class PostSpec:
    source: str
    sentiment: str
    app_topic: str
    subtopic: str
    angle: str
    district_name: str | None = None
    sector: int | None = None
    seed: int = 0
    # Real streets for this quarter (set by the caller from OSM): the engine
    # injects one into the draft and verifies any street the model writes.
    streets: dict | None = None


def sample_specs(count, sources, sentiments, districts, balance="realistic", rng=None):
    """Build ``count`` PostSpecs.

    Args:
        count: how many specs to produce.
        sources: platforms to sample from (e.g. reddit/x/instagram/facebook).
        sentiments: allowed sentiments (e.g. ["negative","positive"] or ["neutral"]).
        districts: list of (name, sector) tuples (defaults; usually overridden later).
        balance: "realistic" skews toward negative civic feedback; "balanced" is even.
        rng: a random.Random for reproducibility.
    """
    rng = rng or random.Random()

    if len(sentiments) <= 1:
        weights = [1.0] * len(sentiments)
    elif balance == "balanced":
        weights = [1.0] * len(sentiments)
    else:  # realistic
        weights = [_REALISTIC_WEIGHTS.get(s, 0.33) for s in sentiments]

    specs = []
    for _ in range(count):
        sentiment = rng.choices(sentiments, weights=weights, k=1)[0]
        app_topic = rng.choice(APP_TOPICS)
        subtopic = rng.choice(SUBTOPICS[app_topic])
        angle = rng.choice(ANGLES.get(sentiment, ANGLES["neutral"]))
        source = rng.choice(sources)
        name, sector = rng.choice(districts) if districts else (None, None)
        specs.append(PostSpec(
            source=source, sentiment=sentiment, app_topic=app_topic, subtopic=subtopic,
            angle=angle, district_name=name, sector=sector, seed=rng.randint(1, 2**31 - 1),
        ))
    return specs
