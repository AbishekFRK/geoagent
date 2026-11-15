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


def test_catalog_resource_lists_places():
    resources = asyncio.run(mcp.list_resources())
    assert any(str(r.uri) == "geoagent://catalog" for r in resources)
    contents = asyncio.run(mcp.read_resource("geoagent://catalog"))
    text = next(iter(contents)).content
    assert len(json.loads(text)) > 10


def test_prompt_is_registered():
    prompts = asyncio.run(mcp.list_prompts())
    assert any(p.name == "geo_question" for p in prompts)
