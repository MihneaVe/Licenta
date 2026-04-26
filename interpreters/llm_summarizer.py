import logging
import os
import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:1B")


class LLMSummarizer:
    """Summarization and insight generation using a local Ollama model.

    Uses gemma3:1B by default — small, fast, good enough for short summaries.
    """

    def __init__(self, model=None, host=None):
        self.model = model or OLLAMA_MODEL
        self.host = host or OLLAMA_HOST
        self.api_url = f"{self.host}/api/generate"

    def _call(self, prompt, max_tokens=256):
        """Send a prompt to Ollama and return the response text."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.3,
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Ollama at {self.host}. Is it running?")
            return ""
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return ""

    def summarize_posts(self, posts_text, district_name="", max_posts=20):
        """Summarize a batch of civic posts into a brief overview.

        Args:
            posts_text: List of post content strings.
            district_name: Optional district name for context.
            max_posts: Max posts to include in prompt (to fit context window).

        Returns:
            Summary string.
        """
        if not posts_text:
            return ""

        combined = "\n---\n".join(posts_text[:max_posts])
        location_ctx = f" in {district_name}" if district_name else ""

        prompt = (
            f"You are analyzing civic complaints and discussions{location_ctx} from social media. "
            f"Summarize the main issues and themes in 3-5 bullet points. Be concise.\n\n"
            f"Posts:\n{combined}\n\n"
            f"Summary:"
        )
        return self._call(prompt, max_tokens=300)

    def generate_district_insight(self, district_name, avg_sentiment, top_topics, post_count):
        """Generate a natural-language insight for a district.

        Args:
            district_name: Name of the district.
            avg_sentiment: Average sentiment score (-1 to +1).
            top_topics: List of (topic_name, count) tuples.
            post_count: Total number of posts analyzed.

        Returns:
            Insight string (1-2 sentences).
        """
        sentiment_desc = (
            "mostly positive" if avg_sentiment > 0.2
            else "mostly negative" if avg_sentiment < -0.2
            else "mixed"
        )
        topics_str = ", ".join(f"{name} ({count})" for name, count in top_topics[:5])

        prompt = (
            f"Write a 2-sentence civic report insight for {district_name}. "
            f"Based on {post_count} social media posts with {sentiment_desc} sentiment. "
            f"Top issue categories: {topics_str}. "
            f"Be factual and concise."
        )
        return self._call(prompt, max_tokens=150)

    def classify_urgency(self, post_text):
        """Classify whether a civic post describes an urgent issue.

        Returns:
            'urgent', 'moderate', or 'low'.
        """
        prompt = (
            f"Classify the urgency of this civic complaint as exactly one word: urgent, moderate, or low.\n\n"
            f"Post: {post_text[:500]}\n\n"
            f"Urgency:"
        )
        result = self._call(prompt, max_tokens=10).lower().strip()

        for level in ("urgent", "moderate", "low"):
            if level in result:
                return level
        return "low"

    def is_available(self):
        """Check if Ollama is running and the model is available."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return any(self.model in m for m in models)
        except Exception:
            pass
        return False
