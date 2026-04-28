import os
import json
from flask import Flask, Response
import geopandas as gpd
import folium
from shapely import wkt
from supabase import create_client, Client
import pandas as pd
from folium.features import GeoJsonTooltip
from flask import Flask, Response

app = Flask(__name__)

# Connection info pulled from env (standard anonymous access)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ujdkiorhdynsrlkhrtcm.supabase.co")
# fallback anon key
SUPABASE_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVqZGtpb3JoZHluc3Jsa2hydGNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM4MjcxNjQsImV4cCI6MjA4OTQwMzE2NH0.P0CFQQD0GFjopsrJ265tm2ieiZPU-WY3XDa-SMiCSks"
)

# Initialize client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sentiment colour mapping from feedbacks (optional enhancement)
SENTIMENT_PALETTE = {
    "Positive": "#22c55e",
    "Negative": "#ef4444",
    "Critical": "#dc2626",
    "Neutral-Positive": "#f59e0b",
    "Negative-Neutral": "#f97316",
}

def fetch_quarters():
    """Fetch Copenhagen quarters from Supabase via REST SDK and return a GeoDataFrame."""
    response = supabase.table("Copenhagen_Quarters").select("kvarternavn, kvarternr, wkb_geometry").execute()
    rows = response.data

    records = []
    for row in rows:
        name = row.get("kvarternavn")
        nr = row.get("kvarternr")
        geom_wkt = row.get("wkb_geometry")
        if geom_wkt:
            try:
                geom = wkt.loads(geom_wkt)
                # Ensure it is a valid shape
                records.append({"name": name, "nr": nr, "geometry": geom})
            except Exception:
                pass  # skip malformed rows

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf


def fetch_feedback_by_quarter(gdf):
    """
    Join feedbacks to quarters by location name matching (best-effort).
    Returns a dict mapping quarter name -> sentiment stats.
    """
    try:
        response = supabase.table("feedbacks").select("location, sentiment_label, sentiment_score").execute()
        rows = response.data

        if not rows:
            return {}

        df = pd.DataFrame(rows)
        stats = df.groupby("location").agg(
            count=("sentiment_score", "count"),
            avg_score=("sentiment_score", "mean")
        ).reset_index()

        return {r["location"]: r for _, r in stats.iterrows()}
    except Exception as e:
        print(f"Feedback fetch error: {e}")
        return {}



def build_map(gdf, feedback_stats):
    """Build and return a folium map HTML string."""
    # Centre on Copenhagen
    centre = [55.6761, 12.5683]
    m = folium.Map(
        location=centre,
        zoom_start=12,
        tiles=None,          # We'll add a custom tile layer
        prefer_canvas=True,
    )

    # Dark CartoDB base tile
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
        name="Dark",
        max_zoom=19,
    ).add_to(m)

    def quarter_style(feature):
        name = feature["properties"].get("name", "")
        stats = feedback_stats.get(name, None)
        if stats is not None:
            score = stats["avg_score"]
            # Red → Yellow → Green based on score (lower score = more negative = more red)
            if score >= 75:
                color = "#22c55e"   # green
            elif score >= 50:
                color = "#f59e0b"   # amber
            else:
                color = "#ef4444"   # red
            opacity = 0.65
        else:
            color = "#3b82f6"       # default blue for quarters with no feedback
            opacity = 0.35

        return {
            "fillColor": color,
            "color": "#94a3b8",
            "weight": 1.5,
            "fillOpacity": opacity,
        }

    def quarter_highlight(feature):
        return {
            "weight": 3,
            "color": "#ffffff",
            "fillOpacity": 0.85,
        }

    # Build GeoJSON
    geojson_data = json.loads(gdf.to_json())

    tooltip = GeoJsonTooltip(
        fields=["name", "nr"],
        aliases=["Quarter:", "Code:"],
        localize=True,
        sticky=False,
        labels=True,
        style=(
            "background-color: #1e293b; color: #f1f5f9; "
            "font-family: Inter, sans-serif; font-size: 12px; "
            "padding: 8px 12px; border-radius: 8px; "
            "box-shadow: 0 4px 6px -1px rgba(0,0,0,.4);"
        ),
    )

    folium.GeoJson(
        geojson_data,
        name="Copenhagen Quarters",
        style_function=quarter_style,
        highlight_function=quarter_highlight,
        tooltip=tooltip,
    ).add_to(m)

    folium.LayerControl().add_to(m)

    # Inject custom CSS to remove the folium default look & make it fill its container
    custom_css = """
    <style>
      html, body, #map {
        width: 100% !important;
        height: 100% !important;
        margin: 0;
        padding: 0;
        background: #0f172a;
      }
      .leaflet-control-attribution {
        font-size: 9px;
        background: rgba(15,23,42,0.7) !important;
        color: #64748b !important;
      }
      .leaflet-control-attribution a { color: #3b82f6; }
      .leaflet-bar a {
        background: #1e293b !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
      }
      .leaflet-bar a:hover { background: #334155 !important; }
    </style>
    """
    m.get_root().header.add_child(folium.Element(custom_css))

    return m.get_root().render()


@app.route("/map")
def serve_map():
    gdf = fetch_quarters()
    feedback_stats = fetch_feedback_by_quarter(gdf)
    html = build_map(gdf, feedback_stats)
    return Response(html, content_type="text/html")


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
