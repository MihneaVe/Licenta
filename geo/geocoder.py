import logging
import time
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class GeocoderService:
    """Geocoding service using Nominatim (OpenStreetMap).

    Resolves location text mentions to lat/lng coordinates.
    Rate-limited to 1 request/second per Nominatim usage policy.
    """

    def __init__(self, user_agent="civicpulse-thesis/1.0"):
        self.geolocator = Nominatim(user_agent=user_agent)
        self.geocode = RateLimiter(
            self.geolocator.geocode,
            min_delay_seconds=1.0,
            max_retries=3,
            error_wait_seconds=5.0,
        )
        self.reverse = RateLimiter(
            self.geolocator.reverse,
            min_delay_seconds=1.0,
            max_retries=3,
            error_wait_seconds=5.0,
        )

    def geocode_location(self, location_text, city="București", country="Romania"):
        """Geocode a location name to coordinates.

        Args:
            location_text: A place name or address (e.g., "Parcul Herăstrău").
            city: City to bias results toward.
            country: Country to bias results toward.

        Returns:
            dict with 'lat', 'lng', 'address' or None if not found.
        """
        query = f"{location_text}, {city}, {country}"
        try:
            location = self.geocode(
                query,
                exactly_one=True,
                language="ro",
                addressdetails=True,
            )
            if location:
                return {
                    "lat": location.latitude,
                    "lng": location.longitude,
                    "address": location.address,
                    "raw": location.raw.get("address", {}),
                }
        except Exception as e:
            logger.warning(f"Geocoding failed for '{location_text}': {e}")
        return None

    def reverse_geocode(self, lat, lng):
        """Reverse geocode coordinates to an address.

        Returns:
            dict with 'address', 'district', 'suburb' or None.
        """
        try:
            location = self.reverse(
                (lat, lng),
                exactly_one=True,
                language="ro",
                addressdetails=True,
            )
            if location:
                address = location.raw.get("address", {})
                return {
                    "address": location.address,
                    "district": (
                        address.get("city_district")
                        or address.get("suburb")
                        or address.get("borough")
                        or ""
                    ),
                    "city": address.get("city", ""),
                    "postcode": address.get("postcode", ""),
                    "raw": address,
                }
        except Exception as e:
            logger.warning(f"Reverse geocoding failed for ({lat}, {lng}): {e}")
        return None

    def batch_geocode(self, location_texts, city="București", country="Romania"):
        """Geocode a list of location names.

        Returns:
            List of (location_text, result) tuples.
        """
        results = []
        for text in location_texts:
            result = self.geocode_location(text, city=city, country=country)
            results.append((text, result))
        return results
