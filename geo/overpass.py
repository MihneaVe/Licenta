import logging
import requests
import time

logger = logging.getLogger(__name__)

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


class OverpassClient:
    """Client for the OpenStreetMap Overpass API.

    Used to query district boundaries, POIs, and infrastructure data.
    Completely free — no API key required.
    """

    def __init__(self, api_url=OVERPASS_API_URL, timeout=60):
        self.api_url = api_url
        self.timeout = timeout

    def query(self, overpass_query):
        """Execute a raw Overpass QL query.

        Args:
            overpass_query: Overpass QL query string.

        Returns:
            JSON response dict or None on failure.
        """
        try:
            response = requests.post(
                self.api_url,
                data={"data": overpass_query},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Overpass query failed: {e}")
            return None

    def get_bucharest_sectors(self):
        """Fetch Bucharest sector boundaries (admin_level=9).

        Returns:
            List of sector elements with geometry data.
        """
        query = """
        [out:json][timeout:60];
        area["name"="București"]["admin_level"="6"]->.bucharest;
        (
          relation(area.bucharest)["admin_level"="9"]["boundary"="administrative"];
        );
        out body;
        >;
        out skel qt;
        """
        return self.query(query)

    def get_pois(self, poi_type, bbox=None):
        """Fetch points of interest in Bucharest.

        Args:
            poi_type: OSM tag value, e.g. 'park', 'bus_stop', 'hospital'.
            bbox: Optional (south, west, north, east) bounding box tuple.
                  Defaults to Bucharest bounds.

        Returns:
            List of POI elements.
        """
        if bbox is None:
            # Approximate Bucharest bounding box
            bbox = (44.35, 25.95, 44.55, 26.20)

        south, west, north, east = bbox
        query = f"""
        [out:json][timeout:60];
        (
          node["leisure"="{poi_type}"]({south},{west},{north},{east});
          way["leisure"="{poi_type}"]({south},{west},{north},{east});
          node["amenity"="{poi_type}"]({south},{west},{north},{east});
          way["amenity"="{poi_type}"]({south},{west},{north},{east});
        );
        out center;
        """
        return self.query(query)

    def get_public_transport_stops(self, bbox=None):
        """Fetch public transport stops in Bucharest."""
        if bbox is None:
            bbox = (44.35, 25.95, 44.55, 26.20)

        south, west, north, east = bbox
        query = f"""
        [out:json][timeout:60];
        (
          node["public_transport"="stop_position"]({south},{west},{north},{east});
          node["highway"="bus_stop"]({south},{west},{north},{east});
          node["railway"="station"]({south},{west},{north},{east});
        );
        out body;
        """
        return self.query(query)

    def get_infrastructure(self, bbox=None):
        """Fetch infrastructure elements (roads, buildings) for analysis."""
        if bbox is None:
            bbox = (44.35, 25.95, 44.55, 26.20)

        south, west, north, east = bbox
        query = f"""
        [out:json][timeout:60];
        (
          way["highway"]["name"]({south},{west},{north},{east});
        );
        out center;
        """
        result = self.query(query)
        if result:
            return result.get("elements", [])
        return []
