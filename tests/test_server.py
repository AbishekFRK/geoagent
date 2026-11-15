import asyncio
import json

from geoagent.server import mcp

EXPECTED_TOOLS = {
    "geocode",
    "distance_bearing",
    "features_within",
    "nearest_features",
    "point_in_polygon",
}


def test_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS
    # Every tool needs a description, because that is what the model reads.
    assert all(t.description for t in tools)


def test_point_in_polygon_tool_accepts_object_and_json_string():
    square = {"type": "Polygon", "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]]}
    for polygon in (square, json.dumps(square)):
        result = asyncio.run(
            mcp.call_tool("point_in_polygon", {"lat": 5, "lon": 5, "polygon_geojson": polygon})
        )
        assert not result.is_error, polygon
        assert "true" in str(result.content[0].text).lower()


def test_catalog_resource_lists_places():
    resources = asyncio.run(mcp.list_resources())
    assert any(str(r.uri) == "geoagent://catalog" for r in resources)
    contents = asyncio.run(mcp.read_resource("geoagent://catalog"))
    text = next(iter(contents)).content
    assert len(json.loads(text)) > 10


def test_prompt_is_registered():
    prompts = asyncio.run(mcp.list_prompts())
    assert any(p.name == "geo_question" for p in prompts)
