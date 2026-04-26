import logging
from transformers import pipeline

logger = logging.getLogger(__name__)

# Multilingual sentiment model — supports Romanian, English, and 8+ languages
MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# Label mapping: the model outputs 'negative', 'neutral', 'positive'
LABEL_MAP = {
    "negative": "Negative",
    "neutral": "Neutral",
    "positive": "Positive",
    # Some versions of the model use LABEL_0/1/2
    "LABEL_0": "Negative",
    "LABEL_1": "Neutral",
    "LABEL_2": "Positive",
}

SCORE_MAP = {
    "Negative": -1.0,
    "Neutral": 0.0,
    "Positive": 1.0,
}


class SentimentModel:
    """Sentiment analysis using cardiffnlp/twitter-xlm-roberta-base-sentiment.

    A multilingual XLM-RoBERTa model fine-tuned on ~198M tweets.
    Runs locally via HuggingFace Transformers — no API calls needed.
    """

    def __init__(self, model_name=MODEL_NAME, device=-1):
        """Initialize the sentiment model.

        Args:
            model_name: HuggingFace model identifier.
            device: -1 for CPU, 0+ for GPU index.
        """
        logger.info(f"Loading sentiment model: {model_name}")
        self.pipe = pipeline(
            "sentiment-analysis",
            model=model_name,
            tokenizer=model_name,
            device=device,
            max_length=512,
            truncation=True,
        )
        logger.info("Sentiment model loaded successfully")

    def predict(self, text):
        """Predict sentiment for a single text.

        Args:
            text: Input text string.

        Returns:
            dict with 'label' (Positive/Negative/Neutral),
            'score' (-1.0 to +1.0), 'confidence' (0.0 to 1.0).
        """
        if not text or not text.strip():
            return {"label": "Neutral", "score": 0.0, "confidence": 0.0}

        result = self.pipe(text[:512])[0]
        raw_label = result["label"].lower() if result["label"].lower() in LABEL_MAP else result["label"]
        label = LABEL_MAP.get(raw_label, "Neutral")
        confidence = result["score"]

        # Convert to continuous score: weight by confidence
        base_score = SCORE_MAP.get(label, 0.0)
        weighted_score = base_score * confidence

        return {
            "label": label,
            "score": round(weighted_score, 4),
            "confidence": round(confidence, 4),
        }

    def predict_batch(self, texts, batch_size=32):
        """Predict sentiment for a batch of texts.

        Args:
            texts: List of text strings.
            batch_size: Batch size for inference.

        Returns:
            List of result dicts (same format as predict()).
        """
        if not texts:
            return []

        truncated = [t[:512] if t else "" for t in texts]
        raw_results = self.pipe(truncated, batch_size=batch_size)

        results = []
        for result in raw_results:
            raw_label = result["label"].lower() if result["label"].lower() in LABEL_MAP else result["label"]
            label = LABEL_MAP.get(raw_label, "Neutral")
            confidence = result["score"]
            base_score = SCORE_MAP.get(label, 0.0)
            weighted_score = base_score * confidence
            results.append({
                "label": label,
                "score": round(weighted_score, 4),
                "confidence": round(confidence, 4),
            })

        return results
