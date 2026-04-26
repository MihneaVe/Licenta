import logging
from transformers import pipeline

logger = logging.getLogger(__name__)

# Multilingual zero-shot classification model
MODEL_NAME = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

# Civic issue categories matching the thesis scope
CIVIC_TOPICS = [
    "infrastructure",
    "cleanliness",
    "safety",
    "transport",
    "greenspace",
    "other",
]

# Multilingual candidate labels (Romanian + English for better matching)
TOPIC_LABELS = {
    "infrastructure": "infrastructură, drumuri, clădiri, construcții, infrastructure, roads, buildings",
    "cleanliness": "curățenie, gunoi, deșeuri, igienă, cleanliness, garbage, waste",
    "safety": "siguranță, criminalitate, pericol, securitate, safety, crime, danger",
    "transport": "transport, trafic, autobuz, metrou, transport, traffic, bus, metro",
    "greenspace": "spații verzi, parc, natură, copaci, mediu, green spaces, park, nature, environment",
    "other": "altele, general, diverse, other, general",
}


class TopicClassifier:
    """Zero-shot topic classification using mDeBERTa for civic issue categories.

    Classifies posts into: infrastructure, cleanliness, safety, transport,
    greenspace, other — without requiring fine-tuned training data.
    """

    def __init__(self, model_name=MODEL_NAME, device=-1):
        logger.info(f"Loading topic classifier: {model_name}")
        self.pipe = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=device,
        )
        self.candidate_labels = list(TOPIC_LABELS.values())
        self.label_names = list(TOPIC_LABELS.keys())
        logger.info("Topic classifier loaded successfully")

    def classify(self, text, threshold=0.15):
        """Classify a text into civic topic categories.

        Args:
            text: Input text string.
            threshold: Minimum confidence score to include a topic.

        Returns:
            List of dicts with 'label' and 'score', sorted by score descending.
        """
        if not text or not text.strip():
            return [{"label": "other", "score": 1.0}]

        result = self.pipe(
            text[:512],
            candidate_labels=self.candidate_labels,
            multi_label=True,
        )

        topics = []
        for label_desc, score in zip(result["labels"], result["scores"]):
            # Map the descriptive label back to the short name
            idx = self.candidate_labels.index(label_desc)
            topic_name = self.label_names[idx]
            if score >= threshold:
                topics.append({"label": topic_name, "score": score})

        topics.sort(key=lambda x: x["score"], reverse=True)
        return topics if topics else [{"label": "other", "score": 1.0}]

    def classify_batch(self, texts, threshold=0.15):
        """Classify a batch of texts.

        Returns:
            List of lists of topic dicts.
        """
        return [self.classify(text, threshold=threshold) for text in texts]
