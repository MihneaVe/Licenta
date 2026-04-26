import re
import unicodedata


def clean_text(text):
    """Clean text for NLP processing — preserves Romanian diacritics."""
    # Remove URLs
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_diacritics(text):
    """Normalize Romanian diacritics (ş→ș, ţ→ț, etc.)."""
    replacements = {
        '\u015f': '\u0219',  # ş → ș
        '\u015e': '\u0218',  # Ş → Ș
        '\u0163': '\u021b',  # ţ → ț
        '\u0162': '\u021a',  # Ţ → Ț
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def tokenize(text):
    """Simple whitespace tokenizer."""
    return text.split()


def remove_stopwords(tokens, stopwords):
    """Remove stopwords from token list."""
    return [token for token in tokens if token not in stopwords]


ROMANIAN_STOPWORDS = {
    "și", "în", "la", "de", "cu", "pe", "din", "care", "este", "sunt",
    "nu", "un", "o", "se", "ce", "mai", "ca", "a", "dar", "sau",
    "pentru", "prin", "fost", "fi", "sa", "au", "cum", "lui", "ei",
    "le", "am", "al", "ale", "s", "era", "când", "despre", "tot",
    "ne", "vă", "mă", "te", "îi", "avea", "fiind", "foarte", "doar",
    "aici", "acum", "sau", "ori", "că", "dacă", "după", "între",
}


def preprocess_text(text, stopwords=None):
    """Full preprocessing pipeline for NLP analysis."""
    if stopwords is None:
        stopwords = ROMANIAN_STOPWORDS

    text = normalize_diacritics(text)
    text = clean_text(text)
    text = text.lower()
    tokens = tokenize(text)
    tokens = remove_stopwords(tokens, stopwords)
    return tokens


def detect_language(text):
    """Detect language of text using langdetect."""
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return "unknown"
