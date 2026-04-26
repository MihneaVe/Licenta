import logging
import random
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class FacebookGroupsScraper:
    """Scrapes public Facebook groups for civic complaints and discussions.

    No login required — only scrapes publicly visible group content.
    Uses Playwright for JavaScript-rendered pages.
    """

    # Public civic-related Facebook groups for Bucharest
    DEFAULT_GROUP_URLS = [
        "https://www.facebook.com/groups/bucuresteni",
        "https://www.facebook.com/groups/problemesector3",
    ]

    def __init__(self, headless=True):
        self.headless = headless
        self.posts = []

    async def _launch_browser(self):
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            locale="ro-RO",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

    async def _close_browser(self):
        if hasattr(self, "browser"):
            await self.browser.close()
        if hasattr(self, "_playwright"):
            await self._playwright.stop()

    async def scrape_group(self, group_url, max_posts=50, scroll_count=10):
        """Scrape posts from a public Facebook group.

        Args:
            group_url: Full URL to the public Facebook group.
            max_posts: Maximum number of posts to collect.
            scroll_count: Number of times to scroll down to load more posts.
        """
        page = await self.context.new_page()

        try:
            await page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Handle cookie consent if present
            try:
                cookie_btn = page.locator(
                    "button[data-cookiebanner='accept_button']"
                )
                if await cookie_btn.count() > 0:
                    await cookie_btn.first.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            # Handle "See more" / login wall for public groups
            try:
                close_btn = page.locator("[aria-label='Close']").first
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            # Extract group name
            group_name = await self._extract_group_name(page, group_url)

            # Scroll to load posts
            for i in range(scroll_count):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(random.uniform(2000, 4000))

            # Extract posts from the feed
            post_elements = await page.locator(
                "div[role='article']"
            ).all()

            for elem in post_elements[:max_posts]:
                try:
                    post = await self._parse_post(elem, group_name, group_url)
                    if post and post["content"]:
                        self.posts.append(post)
                except Exception as e:
                    logger.debug(f"Failed to parse Facebook post: {e}")

            logger.info(
                f"Scraped {len(self.posts)} posts from {group_name}"
            )

        except Exception as e:
            logger.error(f"Failed to scrape group {group_url}: {e}")
        finally:
            await page.close()

    async def _extract_group_name(self, page, group_url):
        try:
            heading = page.locator("h1").first
            if await heading.count() > 0:
                return await heading.inner_text()
        except Exception:
            pass
        # Fallback: extract from URL
        return group_url.rstrip("/").split("/")[-1]

    async def _parse_post(self, element, group_name, group_url):
        """Parse a single post element from a Facebook group."""
        try:
            # Expand "See more" if present
            try:
                see_more = element.locator("div[role='button']", has_text="See more")
                if await see_more.count() > 0:
                    await see_more.first.click()
                    await element.page.wait_for_timeout(500)
            except Exception:
                pass

            # Extract post text
            text_elements = await element.locator(
                "div[data-ad-preview='message'], div[dir='auto']"
            ).all()

            content_parts = []
            for text_el in text_elements:
                try:
                    text = await text_el.inner_text()
                    if text.strip() and len(text.strip()) > 10:
                        content_parts.append(text.strip())
                except Exception:
                    continue

            content = " ".join(content_parts) if content_parts else ""

            if not content or len(content) < 15:
                return None

            # Extract author name
            author = ""
            try:
                author_el = element.locator("strong > span, h3 span a").first
                if await author_el.count() > 0:
                    author = await author_el.inner_text()
            except Exception:
                pass

            # Extract timestamp
            timestamp_text = ""
            try:
                time_el = element.locator("a[role='link'] > span[class]").first
                if await time_el.count() > 0:
                    timestamp_text = await time_el.inner_text()
            except Exception:
                pass

            # Extract reaction count
            reactions = 0
            try:
                reaction_el = element.locator(
                    "span[aria-label*='reaction'], span[aria-label*='like']"
                ).first
                if await reaction_el.count() > 0:
                    label = await reaction_el.get_attribute("aria-label")
                    reactions = int("".join(filter(str.isdigit, label or "0"))) or 0
            except Exception:
                pass

            # Extract comment count
            comment_count = 0
            try:
                comment_el = element.locator("span", has_text="comment").first
                if await comment_el.count() > 0:
                    text = await comment_el.inner_text()
                    comment_count = int("".join(filter(str.isdigit, text or "0"))) or 0
            except Exception:
                pass

            return {
                "source": "facebook",
                "source_id": "",  # Facebook doesn't expose stable IDs in public view
                "group_name": group_name,
                "group_url": group_url,
                "content": content,
                "author": author,
                "timestamp_text": timestamp_text,
                "reactions": reactions,
                "comment_count": comment_count,
                "created_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug(f"Post parse error: {e}")
            return None

    async def scrape_all_defaults(self, max_posts_per_group=30, scroll_count=8):
        """Scrape posts from all default civic groups."""
        await self._launch_browser()
        try:
            for url in self.DEFAULT_GROUP_URLS:
                await self.scrape_group(
                    url, max_posts=max_posts_per_group, scroll_count=scroll_count
                )
                # Random delay between groups
                time.sleep(random.uniform(5, 10))
        finally:
            await self._close_browser()

    def get_posts(self):
        return self.posts

    def clear(self):
        self.posts = []
