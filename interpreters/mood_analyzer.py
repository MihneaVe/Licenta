import logging
from .sentiment_model import SentimentModel
from .topic_classifier import TopicClassifier
from .ner_extractor import NERExtractor

logger = logging.getLogger(__name__)


class MoodAnalyzer:
    """Full NLP analysis pipeline for civic posts.

    Combines sentiment analysis, topic classification, and location
    entity extraction using local HuggingFace models.
    """

    def __init__(self, device=-1):
        """Initialize all NLP models.

        Args:
            device: -1 for CPU, 0+ for GPU index.
        """
        logger.info("Initializing MoodAnalyzer pipeline...")
        self.sentiment = SentimentModel(device=device)
        self.topic_classifier = TopicClassifier(device=device)
        self.ner = NERExtractor()
        logger.info("MoodAnalyzer pipeline ready")

    def analyze(self, text):
        """Run full analysis on a single text.

        Args:
            text: Raw post text.

        Returns:
            dict with sentiment, topics, and location entities.
        """
        if not text or not text.strip():
            return {
                "sentiment": {"label": "Neutral", "score": 0.0, "confidence": 0.0},
                "topics": [],
                "topic_scores": {},
                "locations": [],
            }

        sentiment = self.sentiment.predict(text)
        topics = self.topic_classifier.classify(text)
        locations = self.ner.extract_locations(text)

        return {
            "sentiment": sentiment,
            "topics": [t["label"] for t in topics if t["score"] > 0.3],
            "topic_scores": {t["label"]: round(t["score"], 4) for t in topics},
            "locations": locations,
        }

    def analyze_batch(self, texts, batch_size=32):
        """Run analysis on a batch of texts.

        Args:
            texts: List of text strings.
            batch_size: Batch size for model inference.

        Returns:
            List of analysis result dicts.
        """
        if not texts:
            return []

        sentiments = self.sentiment.predict_batch(texts, batch_size=batch_size)
        results = []

        for i, text in enumerate(texts):
            topics = self.topic_classifier.classify(text)
            locations = self.ner.extract_locations(text)

            results.append({
                "sentiment": sentiments[i],
                "topics": [t["label"] for t in topics if t["score"] > 0.3],
                "topic_scores": {t["label"]: round(t["score"], 4) for t in topics},
                "locations": locations,
            })

        return results
