import json

import httpx
import pytest
from starlette.testclient import TestClient

from geoagent import web

client = TestClient(web.app)

GEOCODE_BLR = json.dumps({"name": "Bengaluru", "code": None, "kind": "city", "lat": 12.9716, "lon": 77.5946}, indent=2)
SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]]}


def two_airports_text():
    # MCP returns a list tool's items as separate JSON objects in one text block.
    a = {"name": "Kempegowda Airport", "code": "BLR", "kind": "airport", "lat": 13.1979, "lon": 77.7063, "distance_km": 27.8}
    b = {"name": "Coimbatore Airport", "code": "CJB", "kind": "airport", "lat": 11.03, "lon": 77.0434, "distance_km": 223.0}
    return json.dumps(a, indent=2) + "\n" + json.dumps(b, indent=2)


# ------------------------------------------------------------------ map_layers


def test_geocode_becomes_a_point():
    layers = web.map_layers([{"name": "geocode", "arguments": {"place": "Bengaluru"}, "result": GEOCODE_BLR}])
    assert layers["points"] == [{"lat": 12.9716, "lon": 77.5946, "label": "Bengaluru", "kind": "geocoded"}]


def test_distance_becomes_a_labelled_line():
    call = {
        "name": "distance_bearing",
        "arguments": {"lat1": 1, "lon1": 2, "lat2": 3, "lon2": 4},
        "result": json.dumps({"distance_km": 290.5, "initial_bearing_deg": 87.3, "final_bearing_deg": 87.9}),
    }
    line = web.map_layers([call])["lines"][0]
    assert line["from"] == [1.0, 2.0] and line["to"] == [3.0, 4.0]
    assert "290.5 km" in line["label"]
    assert line["distance_km"] == 290.5 and line["bearing_deg"] == 87.3  # numbers for the UI's stat chips


def test_list_results_and_radius_circle():
    call = {"name": "features_within", "arguments": {"lat": 12.97, "lon": 77.59, "radius_km": 300}, "result": two_airports_text()}
    layers = web.map_layers([call])
    assert [p["label"] for p in layers["points"]] == ["Kempegowda Airport (27.8 km)", "Coimbatore Airport (223.0 km)"]
    assert layers["circles"] == [{"lat": 12.97, "lon": 77.59, "radius_km": 300.0}]


def test_polygon_object_and_json_string_both_work():
    for polygon in (SQUARE, json.dumps(SQUARE)):
        call = {"name": "point_in_polygon", "arguments": {"lat": 5, "lon": 5, "polygon_geojson": polygon}, "result": "true"}
        layers = web.map_layers([call])
        assert layers["polygons"] == [{"geojson": SQUARE, "inside": True}]
        assert layers["points"][0]["kind"] == "inside"


def test_failed_calls_and_odd_arguments_are_skipped_not_fatal():
    calls = [
        {"name": "geocode", "arguments": {}, "result": "ERROR: boom"},
        {"name": "distance_bearing", "arguments": "not a dict", "result": "{}"},
        {"name": "distance_bearing", "arguments": {"lat1": "x"}, "result": json.dumps({"distance_km": 1})},
        {"name": "unknown_tool", "arguments": {}, "result": "{}"},
    ]
    assert web.map_layers(calls) == {"points": [], "lines": [], "circles": [], "polygons": []}


def test_duplicate_points_are_drawn_once():
    call = {"name": "geocode", "arguments": {}, "result": GEOCODE_BLR}
    assert len(web.map_layers([call, call])["points"]) == 1


# ------------------------------------------------------------------ HTTP routes


def test_index_serves_the_page_and_escapes_nothing_unsafe():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<title>GeoAgent</title>" in resp.text
    # Model and tool text must be inserted as text, never as HTML.
    assert "innerHTML = text" not in resp.text


def test_places_endpoint_lists_the_dataset():
    data = client.get("/api/places").json()
    assert len(data) > 10 and {"name", "lat", "lon"} <= set(data[0])


def test_models_endpoint_falls_back_to_the_default_when_the_server_is_down(monkeypatch):
    monkeypatch.setenv("GEOAGENT_BASE_URL", "http://127.0.0.1:9/v1")  # nothing listens on port 9
    monkeypatch.setenv("GEOAGENT_MODEL", "my-model")
    info = client.get("/api/models").json()
    assert info == {"default": "my-model", "models": ["my-model"], "server_reachable": False}


@pytest.mark.parametrize(
    "body",
    [{}, {"question": ""}, {"question": "   "}, {"question": 5}, {"question": "x" * 601}, {"question": "ok", "model": 3}],
)
def test_ask_rejects_bad_input(body):
    resp = client.post("/api/ask", json=body)
    assert resp.status_code == 400 and resp.json()["error"]


def test_ask_rejects_non_json_body():
    assert client.post("/api/ask", content=b"not json").status_code == 400


def test_ask_returns_answer_tool_calls_and_map_layers(monkeypatch):
    async def fake(question, *, model=None, **_):
        assert question == "How far?" and model == "m1"
        return {
            "answer": "290.5 km",
            "model": model,
            "steps": 2,
            "tool_calls": [{"name": "geocode", "arguments": {"place": "Bengaluru"}, "result": GEOCODE_BLR}],
        }

    monkeypatch.setattr(web.agent, "ask_async", fake)
    data = client.post("/api/ask", json={"question": "  How far?  ", "model": "m1"}).json()
    assert data["answer"] == "290.5 km"
    assert data["layers"]["points"][0]["label"] == "Bengaluru"


def test_ask_reports_an_unreachable_model_server_clearly(monkeypatch):
    async def down(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(web.agent, "ask_async", down)
    resp = client.post("/api/ask", json={"question": "hi"})
    assert resp.status_code == 502
    assert "Ollama" in resp.json()["error"]


def test_ask_turns_unexpected_failures_into_a_json_error(monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(web.agent, "ask_async", broken)
    resp = client.post("/api/ask", json={"question": "hi"})
    assert resp.status_code == 500 and "kaboom" in resp.json()["error"]
