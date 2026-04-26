import logging
import re

logger = logging.getLogger(__name__)


class NERExtractor:
    """Named Entity Recognition for location extraction using spaCy.

    Extracts location entities (streets, neighborhoods, landmarks) from
    Romanian and English text for geocoding.
    """

    def __init__(self, model_name="ro_core_news_sm"):
        """Initialize spaCy NER model.

        Args:
            model_name: spaCy model name. Default is Romanian small model.
                        Falls back to multilingual if Romanian model unavailable.
        """
        import spacy

        try:
            self.nlp = spacy.load(model_name)
            logger.info(f"Loaded spaCy model: {model_name}")
        except OSError:
            logger.warning(
                f"spaCy model '{model_name}' not found. "
                "Falling back to 'xx_ent_wiki_sm' (multilingual)."
            )
            try:
                self.nlp = spacy.load("xx_ent_wiki_sm")
            except OSError:
                logger.warning(
                    "No spaCy model found. Using blank Romanian model. "
                    "Install with: python -m spacy download ro_core_news_sm"
                )
                self.nlp = spacy.blank("ro")

        # Common Bucharest location keywords for pattern-based fallback
        self._location_patterns = [
            r"\b[Ss]ector(?:ul)?\s*[1-6]\b",
            r"\b[Ss]tr(?:ada)?\.?\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+(?:\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+)*\b",
            r"\b[Bb]ulevardul\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+(?:\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+)*\b",
            r"\b[Pp]arcul\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+\b",
            r"\b[Pp]iața\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+\b",
            r"\b[Cc]alea\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+(?:\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+)*\b",
            r"\b[Șș]oseaua\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+(?:\s+[A-ZĂÂÎȘȚ][a-zăâîșț]+)*\b",
        ]

    def extract_locations(self, text):
        """Extract location entities from text.

        Uses spaCy NER with pattern-based fallback for Romanian addresses.

        Args:
            text: Input text string.

        Returns:
            List of dicts with 'text', 'label', 'start', 'end'.
        """
        if not text or not text.strip():
            return []

        locations = []
        seen_texts = set()

        # spaCy NER extraction
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ("LOC", "GPE", "FAC", "ORG"):
                normalized = ent.text.strip()
                if normalized.lower() not in seen_texts:
                    locations.append({
                        "text": normalized,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    })
                    seen_texts.add(normalized.lower())

        # Pattern-based extraction for Romanian street/location names
        for pattern in self._location_patterns:
            for match in re.finditer(pattern, text):
                matched_text = match.group().strip()
                if matched_text.lower() not in seen_texts:
                    locations.append({
                        "text": matched_text,
                        "label": "LOC_PATTERN",
                        "start": match.start(),
                        "end": match.end(),
                    })
                    seen_texts.add(matched_text.lower())

        return locations

    def extract_locations_batch(self, texts):
        """Extract locations from a batch of texts.

        Returns:
            List of lists of location dicts.
        """
        return [self.extract_locations(text) for text in texts]
