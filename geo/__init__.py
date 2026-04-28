"""Lazy re-exports.

Importing the geo package by itself doesn't pull in geopy / shapely so
callers that only need the Overpass client (which has no heavy deps)
can ``from geo.overpass import OverpassClient`` without installing the
full geo stack.
"""

from __future__ import annotations

__all__ = ["GeocoderService", "DistrictMapper", "OverpassClient"]


def __getattr__(name):  # PEP 562 lazy module attributes
    if name == "GeocoderService":
        from .geocoder import GeocoderService
        return GeocoderService
    if name == "DistrictMapper":
        from .districts import DistrictMapper
        return DistrictMapper
    if name == "OverpassClient":
        from .overpass import OverpassClient
        return OverpassClient
    raise AttributeError(f"module 'geo' has no attribute {name!r}")
