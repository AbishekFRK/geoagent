"""GeoAgent MCP server (stdio). Wraps the pure functions in geoagent.geo as MCP tools.

Built on the MCP Python SDK 2.x (MCPServer, formerly FastMCP in 1.x).
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from . import geo

mcp = MCPServer("GeoAgent")


@mcp.tool()
def geocode(place: str) -> dict:
    """Look up a place by name or airport code (e.g. "Bengaluru", "BLR") in the bundled dataset.

    Returns name, kind, lat and lon, or an error message if nothing matches.
    """
    found = geo.find_place(place)
    if found is None:
        return {"error": f"No place matching '{place}' in the sample dataset."}
    return found.as_dict()


@mcp.tool()
def distance_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Geodesic distance in km and bearings in degrees from point 1 to point 2 (WGS84)."""
    return geo.distance_bearing(lat1, lon1, lat2, lon2)


@mcp.tool()
def features_within(lat: float, lon: float, radius_km: float, kind: str | None = None) -> list[dict]:
    """List places within radius_km of a point, nearest first. kind can be "city" or "airport"."""
    return geo.features_within(lat, lon, radius_km, kind)


@mcp.tool()
def nearest_features(lat: float, lon: float, n: int = 3, kind: str | None = None) -> list[dict]:
    """The n nearest places to a point. kind can be "city" or "airport"."""
    return geo.nearest_features(lat, lon, n, kind)


@mcp.tool()
def point_in_polygon(lat: float, lon: float, polygon_geojson: dict | str) -> bool:
    """True if the point is inside a GeoJSON Polygon or MultiPolygon (GeoJSON is lon, lat order).

    polygon_geojson is the GeoJSON object itself or a JSON string of it.
    """
    return geo.point_in_polygon(lat, lon, polygon_geojson)


# TODO (v0.2): elevation_profile(line) using an open DEM such as SRTM.


@mcp.resource("geoagent://catalog")
def catalog() -> str:
    """The dataset the tools search: every place with its kind and coordinates."""
    return json.dumps([p.as_dict() for p in geo.load_places()], indent=2)


@mcp.prompt()
def geo_question(question: str) -> str:
    """A system-style prompt that tells the model how to use the GeoAgent tools."""
    return (
        "You are a careful geospatial assistant. Use the GeoAgent tools for every "
        "coordinate, distance or proximity fact; never estimate them from memory. "
        "Geocode place names first, state distances in km, and if the question is "
        "ambiguous or the place is not in the dataset, say so and ask instead of guessing.\n\n"
        f"Question: {question}"
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
