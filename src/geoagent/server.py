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

    Returns the place's name, kind, lat and lon, or an error if nothing matches. It returns
    coordinates only, never distances: to get a distance or bearing, call distance_bearing
    next. Always call this first for any place name instead of using remembered coordinates.
    """
    found = geo.find_place(place)
    if found is None:
        return {"error": f"No place matching '{place}' in the sample dataset."}
    return found.as_dict()


@mcp.tool()
def distance_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Geodesic distance in km and bearings in degrees from point 1 to point 2 (WGS84).

    Use this for every distance or bearing question. Never estimate a distance from memory.
    Get the coordinates from geocode first.
    """
    return geo.distance_bearing(lat1, lon1, lat2, lon2)


@mcp.tool()
def features_within(lat: float, lon: float, radius_km: float, kind: str | None = None) -> list[dict]:
    """List all places within radius_km of a point, nearest first. kind can be "city" or "airport".

    Use for "what is within X km of ..." questions. Get the point from geocode first.
    """
    return geo.features_within(lat, lon, radius_km, kind)


@mcp.tool()
def nearest_features(lat: float, lon: float, n: int = 3, kind: str | None = None) -> list[dict]:
    """The n nearest places to a point. kind can be "city" or "airport".

    Use for "closest" or "nearest" questions. Get the point from geocode first.
    """
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
        "You are a careful geospatial assistant. Follow these rules.\n"
        "1. Turn every place name into coordinates with the geocode tool. Never use "
        "coordinates or distances from memory.\n"
        "2. geocode returns coordinates only. For any distance or bearing, you must then "
        "call distance_bearing.\n"
        "3. Use nearest_features for 'closest' questions and features_within for "
        "'within X km' questions.\n"
        "4. If the question does not name the specific places it needs, or geocode cannot "
        "find a place, say so and ask the user. Never pick places yourself and never invent "
        "coordinates.\n"
        "5. Report the tool's numbers in km and keep the answer short.\n\n"
        f"Question: {question}"
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
