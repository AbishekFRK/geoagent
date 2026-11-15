"""Pure geospatial functions. No MCP, no I/O beyond loading the bundled sample data.

Every function takes and returns plain Python types so it is easy to unit-test
and easy for an LLM to read the result. Coordinates are WGS84 degrees,
latitude first. GeoJSON inputs follow the GeoJSON convention (longitude first).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from pyproj import Geod
from shapely.geometry import Point, shape

_GEOD = Geod(ellps="WGS84")


@dataclass(frozen=True)
class Place:
    name: str
    code: str
    kind: str
    lat: float
    lon: float

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "code": self.code or None,
            "kind": self.kind,
            "lat": self.lat,
            "lon": self.lon,
        }


def _check_coord(lat: float, lon: float) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"latitude {lat} is outside -90..90")
    if not -180 <= lon <= 180:
        raise ValueError(f"longitude {lon} is outside -180..180")


@lru_cache(maxsize=1)
def load_places() -> tuple[Place, ...]:
    """Load the bundled sample dataset (replace with Natural Earth / OSM later)."""
    text = resources.files("geoagent").joinpath("data/sample_places.csv").read_text(encoding="utf-8")
    rows = csv.DictReader(text.splitlines())
    return tuple(
        Place(r["name"], r["code"], r["kind"], float(r["lat"]), float(r["lon"])) for r in rows
    )


def find_place(query: str) -> Place | None:
    """Find a place by exact code, exact name, or unique name substring (case-insensitive)."""
    q = query.strip().lower()
    places = load_places()
    for p in places:
        if p.code and p.code.lower() == q:
            return p
    for p in places:
        if p.name.lower() == q:
            return p
    matches = [p for p in places if q in p.name.lower()]
    # Prefer a city over an airport when the substring is ambiguous, e.g. "Bengaluru".
    matches.sort(key=lambda p: (p.kind != "city", len(p.name)))
    return matches[0] if matches else None


def distance_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Geodesic distance (WGS84 ellipsoid) and bearings from point 1 to point 2."""
    _check_coord(lat1, lon1)
    _check_coord(lat2, lon2)
    fwd, back, dist_m = _GEOD.inv(lon1, lat1, lon2, lat2)
    return {
        "distance_km": round(dist_m / 1000, 3),
        "initial_bearing_deg": round(fwd % 360, 2),
        "final_bearing_deg": round((back + 180) % 360, 2),
    }


def _with_distance(lat: float, lon: float, places) -> list[dict]:
    out = []
    for p in places:
        _, _, d = _GEOD.inv(lon, lat, p.lon, p.lat)
        out.append({**p.as_dict(), "distance_km": round(d / 1000, 3)})
    return sorted(out, key=lambda r: r["distance_km"])


def features_within(lat: float, lon: float, radius_km: float, kind: str | None = None) -> list[dict]:
    """All sample features within radius_km of a point, nearest first."""
    _check_coord(lat, lon)
    if radius_km < 0:
        raise ValueError("radius_km must be >= 0")
    places = [p for p in load_places() if kind is None or p.kind == kind]
    return [r for r in _with_distance(lat, lon, places) if r["distance_km"] <= radius_km]


def nearest_features(lat: float, lon: float, n: int = 3, kind: str | None = None) -> list[dict]:
    """The n nearest sample features to a point."""
    _check_coord(lat, lon)
    if n < 1:
        raise ValueError("n must be >= 1")
    places = [p for p in load_places() if kind is None or p.kind == kind]
    return _with_distance(lat, lon, places)[:n]


def point_in_polygon(lat: float, lon: float, polygon_geojson: dict) -> bool:
    """True if the point lies inside (or on the edge of) a GeoJSON Polygon/MultiPolygon."""
    _check_coord(lat, lon)
    geom = shape(polygon_geojson)
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"expected a Polygon or MultiPolygon, got {geom.geom_type}")
    return bool(geom.covers(Point(lon, lat)))
