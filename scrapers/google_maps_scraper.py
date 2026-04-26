import logging
import json
import time
import random
from datetime import datetime

logger = logging.getLogger(__name__)


class GoogleMapsScraper:
    """Scrapes reviews from Google Maps places using Playwright.

    Targets parks, metro stations, government offices, markets, and other
    civic-relevant locations in Bucharest.
    """

    # Civic-relevant place types to scrape in Bucharest
    DEFAULT_PLACE_URLS = [
        # Parks
        "https://www.google.com/maps/place/Parcul+Herăstrău",
        "https://www.google.com/maps/place/Parcul+Cișmigiu",
        "https://www.google.com/maps/place/Parcul+Tineretului",
        "https://www.google.com/maps/place/Parcul+IOR",
        # Metro stations
        "https://www.google.com/maps/place/Stația+de+metrou+Piața+Unirii",
        "https://www.google.com/maps/place/Stația+de+metrou+Victoriei",
        # District town halls
        "https://www.google.com/maps/place/Primăria+Sectorului+1",
        "https://www.google.com/maps/place/Primăria+Sectorului+3",
    ]

    def __init__(self, headless=True):
        self.headless = headless
        self.reviews = []

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

    async def scrape_place(self, place_url, max_reviews=50):
        """Scrape reviews from a single Google Maps place URL.

        Args:
            place_url: Full Google Maps URL for the place.
            max_reviews: Maximum number of reviews to collect.
        """
        page = await self.context.new_page()

        try:
            await page.goto(place_url, wait_until="networkidle", timeout=30000)

            # Accept cookies dialog if present
            try:
                accept_btn = page.locator("button", has_text="Accept all")
                if await accept_btn.count() > 0:
                    await accept_btn.first.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            # Extract place name and coordinates from the page
            place_name = await self._extract_place_name(page)
            coordinates = await self._extract_coordinates(page)

            # Click the reviews tab/button
            try:
                reviews_tab = page.locator("button[aria-label*='Reviews']").first
                if await reviews_tab.count() == 0:
                    reviews_tab = page.locator("button[aria-label*='recenzii']").first
                await reviews_tab.click()
                await page.wait_for_timeout(2000)
            except Exception:
                logger.warning(f"Could not click reviews tab for {place_url}")
                await page.close()
                return

            # Scroll the reviews panel to load more
            reviews_panel = page.locator("div[class*='review']").first
            for _ in range(max_reviews // 10):
                try:
                    await reviews_panel.evaluate("el => el.scrollTop = el.scrollHeight")
                    await page.wait_for_timeout(random.uniform(1000, 2000))
                except Exception:
                    break

            # Extract individual reviews
            review_elements = await page.locator(
                "div[data-review-id]"
            ).all()

            for elem in review_elements[:max_reviews]:
                try:
                    review = await self._parse_review(elem, place_name, coordinates, place_url)
                    if review:
                        self.reviews.append(review)
                except Exception as e:
                    logger.debug(f"Failed to parse review: {e}")

            logger.info(
                f"Scraped {len(review_elements[:max_reviews])} reviews from {place_name}"
            )

        except Exception as e:
            logger.error(f"Failed to scrape {place_url}: {e}")
        finally:
            await page.close()

    async def _extract_place_name(self, page):
        try:
            name_el = page.locator("h1").first
            return await name_el.inner_text()
        except Exception:
            return "Unknown Place"

    async def _extract_coordinates(self, page):
        """Extract lat/lng from the URL after page loads."""
        try:
            url = page.url
            if "@" in url:
                coords_part = url.split("@")[1].split(",")
                return {
                    "lat": float(coords_part[0]),
                    "lng": float(coords_part[1]),
                }
        except Exception:
            pass
        return None

    async def _parse_review(self, element, place_name, coordinates, place_url):
        """Parse a single review element into a structured dict."""
        try:
            # Review text — may need to expand "More" button
            try:
                more_btn = element.locator("button", has_text="More")
                if await more_btn.count() > 0:
                    await more_btn.first.click()
                    await element.page.wait_for_timeout(300)
            except Exception:
                pass

            text_el = element.locator("span[class*='review-full-text'], span.wiI7pd")
            content = await text_el.first.inner_text() if await text_el.count() > 0 else ""

            if not content.strip():
                return None

            # Rating
            rating = None
            try:
                star_el = element.locator("span[aria-label*='star'], span[aria-label*='stea']")
                if await star_el.count() > 0:
                    label = await star_el.first.get_attribute("aria-label")
                    rating = int(label[0]) if label else None
            except Exception:
                pass

            # Author
            author = ""
            try:
                author_el = element.locator("div[class*='d4r55']")
                if await author_el.count() > 0:
                    author = await author_el.first.inner_text()
            except Exception:
                pass

            # Relative time (e.g., "2 months ago")
            timestamp = ""
            try:
                time_el = element.locator("span[class*='rsqaWe']")
                if await time_el.count() > 0:
                    timestamp = await time_el.first.inner_text()
            except Exception:
                pass

            review_id = await element.get_attribute("data-review-id") or ""

            return {
                "source": "google_maps",
                "source_id": review_id,
                "place_name": place_name,
                "place_url": place_url,
                "content": content.strip(),
                "rating": rating,
                "author": author,
                "timestamp_text": timestamp,
                "coordinates": coordinates,
                "created_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug(f"Review parse error: {e}")
            return None

    async def scrape_all_defaults(self, max_reviews_per_place=30):
        """Scrape reviews from all default civic places."""
        await self._launch_browser()
        try:
            for url in self.DEFAULT_PLACE_URLS:
                await self.scrape_place(url, max_reviews=max_reviews_per_place)
                # Random delay between places to avoid rate limiting
                await self.context.pages[0].wait_for_timeout(
                    random.uniform(3000, 6000)
                ) if self.context.pages else time.sleep(random.uniform(3, 6))
        finally:
            await self._close_browser()

    def get_reviews(self):
        return self.reviews

    def get_posts(self):
        """Unified interface — returns reviews in post-like format."""
        return self.reviews

    def clear(self):
        self.reviews = []
