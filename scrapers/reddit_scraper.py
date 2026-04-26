import praw
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RedditScraper:
    """Scrapes posts and comments from Romanian city subreddits using PRAW."""

    DEFAULT_SUBREDDITS = [
        "bucuresti",
        "Romania",
        "Cluj",
    ]

    def __init__(self, client_id, client_secret, user_agent="civicpulse-thesis/1.0"):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self.posts = []

    def scrape_subreddit(self, subreddit_name, sort="hot", limit=100, time_filter="week"):
        """Scrape posts from a single subreddit.

        Args:
            subreddit_name: Name of the subreddit (without r/).
            sort: One of 'hot', 'new', 'top', 'rising'.
            limit: Maximum number of posts to fetch.
            time_filter: For 'top' sort — 'hour', 'day', 'week', 'month', 'year', 'all'.
        """
        subreddit = self.reddit.subreddit(subreddit_name)

        if sort == "hot":
            submissions = subreddit.hot(limit=limit)
        elif sort == "new":
            submissions = subreddit.new(limit=limit)
        elif sort == "top":
            submissions = subreddit.top(time_filter=time_filter, limit=limit)
        elif sort == "rising":
            submissions = subreddit.rising(limit=limit)
        else:
            submissions = subreddit.hot(limit=limit)

        for submission in submissions:
            post = {
                "source": "reddit",
                "source_id": submission.id,
                "subreddit": subreddit_name,
                "title": submission.title,
                "content": submission.selftext,
                "author": str(submission.author) if submission.author else "[deleted]",
                "score": submission.score,
                "num_comments": submission.num_comments,
                "url": submission.url,
                "permalink": f"https://reddit.com{submission.permalink}",
                "created_at": datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                "flair": submission.link_flair_text,
            }
            self.posts.append(post)

        logger.info(f"Scraped {len(self.posts)} posts from r/{subreddit_name}")

    def scrape_comments(self, submission_id, limit=50):
        """Scrape top-level comments from a specific submission."""
        submission = self.reddit.submission(id=submission_id)
        submission.comments.replace_more(limit=0)

        comments = []
        for comment in submission.comments.list()[:limit]:
            comments.append({
                "source": "reddit",
                "source_id": comment.id,
                "parent_id": submission_id,
                "content": comment.body,
                "author": str(comment.author) if comment.author else "[deleted]",
                "score": comment.score,
                "created_at": datetime.utcfromtimestamp(comment.created_utc).isoformat(),
            })
        return comments

    def search(self, query, subreddit_name=None, sort="relevance", limit=100):
        """Search Reddit for posts matching a query.

        Args:
            query: Search query string.
            subreddit_name: Optional — limit search to a specific subreddit.
            sort: 'relevance', 'hot', 'top', 'new', 'comments'.
            limit: Maximum results.
        """
        if subreddit_name:
            subreddit = self.reddit.subreddit(subreddit_name)
            results = subreddit.search(query, sort=sort, limit=limit)
        else:
            results = self.reddit.subreddit("all").search(
                query, sort=sort, limit=limit
            )

        search_posts = []
        for submission in results:
            post = {
                "source": "reddit",
                "source_id": submission.id,
                "subreddit": submission.subreddit.display_name,
                "title": submission.title,
                "content": submission.selftext,
                "author": str(submission.author) if submission.author else "[deleted]",
                "score": submission.score,
                "num_comments": submission.num_comments,
                "url": submission.url,
                "permalink": f"https://reddit.com{submission.permalink}",
                "created_at": datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                "flair": submission.link_flair_text,
            }
            search_posts.append(post)
        return search_posts

    def scrape_all_defaults(self, sort="new", limit=50):
        """Scrape posts from all default subreddits."""
        for sub in self.DEFAULT_SUBREDDITS:
            try:
                self.scrape_subreddit(sub, sort=sort, limit=limit)
            except Exception as e:
                logger.error(f"Failed to scrape r/{sub}: {e}")

    def get_posts(self):
        return self.posts

    def clear(self):
        self.posts = []
