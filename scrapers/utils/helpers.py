import re
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_text_from_html(html_content):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text()


def clean_text(text):
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()


def save_scraped_data(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_scraped_data(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_post(raw_post, source):
    """Normalize a scraped post into a unified format for the pipeline.

    Returns a dict with keys: source, source_id, content, author, score,
    coordinates, created_at, extra.
    """
    normalized = {
        "source": source,
        "source_id": raw_post.get("source_id", ""),
        "content": "",
        "author": raw_post.get("author", ""),
        "score": 0,
        "coordinates": None,
        "created_at": raw_post.get("created_at", datetime.utcnow().isoformat()),
        "extra": {},
    }

    if source == "reddit":
        title = raw_post.get("title", "")
        body = raw_post.get("content", "")
        normalized["content"] = f"{title}. {body}".strip() if body else title
        normalized["score"] = raw_post.get("score", 0)
        normalized["extra"] = {
            "subreddit": raw_post.get("subreddit", ""),
            "flair": raw_post.get("flair"),
            "num_comments": raw_post.get("num_comments", 0),
            "permalink": raw_post.get("permalink", ""),
        }

    elif source == "google_maps":
        normalized["content"] = raw_post.get("content", "")
        normalized["score"] = raw_post.get("rating", 0) or 0
        normalized["coordinates"] = raw_post.get("coordinates")
        normalized["extra"] = {
            "place_name": raw_post.get("place_name", ""),
            "place_url": raw_post.get("place_url", ""),
            "rating": raw_post.get("rating"),
            "timestamp_text": raw_post.get("timestamp_text", ""),
        }

    elif source == "facebook":
        normalized["content"] = raw_post.get("content", "")
        normalized["score"] = raw_post.get("reactions", 0)
        normalized["extra"] = {
            "group_name": raw_post.get("group_name", ""),
            "group_url": raw_post.get("group_url", ""),
            "reactions": raw_post.get("reactions", 0),
            "comment_count": raw_post.get("comment_count", 0),
            "timestamp_text": raw_post.get("timestamp_text", ""),
        }

    return normalized


def deduplicate_posts(posts):
    """Remove duplicate posts based on source + source_id."""
    seen = set()
    unique = []
    for post in posts:
        key = (post.get("source", ""), post.get("source_id", ""))
        if key not in seen:
            seen.add(key)
            unique.append(post)
    return unique
