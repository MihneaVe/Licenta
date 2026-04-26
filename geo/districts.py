import logging
import json
from shapely.geometry import Point, shape
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

# Bucharest sector/district boundaries as simplified bounding info.
# In production, load actual GeoJSON from OSM via the OverpassClient.
BUCHAREST_SECTORS = {
    "Sector 1": {"admin_level": "9", "osm_id": 0},
    "Sector 2": {"admin_level": "9", "osm_id": 0},
    "Sector 3": {"admin_level": "9", "osm_id": 0},
    "Sector 4": {"admin_level": "9", "osm_id": 0},
    "Sector 5": {"admin_level": "9", "osm_id": 0},
    "Sector 6": {"admin_level": "9", "osm_id": 0},
}


class DistrictMapper:
    """Maps coordinates to Bucharest districts (sectors).

    Loads district boundary polygons from GeoJSON and uses Shapely
    for point-in-polygon checks.
    """

    def __init__(self, geojson_path=None):
        self.districts = {}  # name -> shapely Polygon
        if geojson_path:
            self.load_boundaries(geojson_path)

    def load_boundaries(self, geojson_path):
        """Load district boundaries from a GeoJSON file.

        Expected format: FeatureCollection where each feature has
        a 'name' property and a Polygon/MultiPolygon geometry.
        """
        try:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for feature in data.get("features", []):
                name = (
                    feature.get("properties", {}).get("name")
                    or feature.get("properties", {}).get("local_name")
                    or "Unknown"
                )
                geometry = shape(feature["geometry"])
                self.districts[name] = geometry

            logger.info(f"Loaded {len(self.districts)} district boundaries")
        except Exception as e:
            logger.error(f"Failed to load district boundaries: {e}")

    def load_boundaries_from_osm(self, city="București"):
        """Load district boundaries directly from OpenStreetMap via osmnx.

        Requires osmnx to be installed.
        """
        try:
            import osmnx as ox

            # Get administrative boundaries for sectors (admin_level 9 in Bucharest)
            gdf = ox.features_from_place(
                city,
                tags={"admin_level": "9", "boundary": "administrative"},
            )

            for _, row in gdf.iterrows():
                name = row.get("name", "Unknown")
                if hasattr(row, "geometry") and row.geometry is not None:
                    self.districts[name] = row.geometry

            logger.info(
                f"Loaded {len(self.districts)} district boundaries from OSM"
            )
        except Exception as e:
            logger.error(f"Failed to load OSM boundaries: {e}")

    def get_district(self, lat, lng):
        """Determine which district a point falls in.

        Args:
            lat: Latitude.
            lng: Longitude.

        Returns:
            District name string or None if not found.
        """
        point = Point(lng, lat)  # Shapely uses (x=lng, y=lat)
        for name, polygon in self.districts.items():
            if polygon.contains(point):
                return name
        return None

    def get_all_district_names(self):
        return list(self.districts.keys())

    def save_boundaries_geojson(self, output_path):
        """Export loaded boundaries as GeoJSON."""
        from shapely.geometry import mapping

        features = []
        for name, geom in self.districts.items():
            features.append({
                "type": "Feature",
                "properties": {"name": name},
                "geometry": mapping(geom),
            })

        geojson = {"type": "FeatureCollection", "features": features}
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
