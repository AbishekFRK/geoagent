"""Small local web UI for GeoAgent: ask a question, see the answer, the tool calls and a map.

    geoagent-web                 # then open http://127.0.0.1:8000
    geoagent-web --port 9000

The page talks to this server, which runs the same agent loop as `python -m geoagent.agent`.
It binds to localhost by default, because it can drive your model server and has no login.
"""

from __future__ import annotations

import argparse
import json
import os
from importlib import resources
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from . import agent, geo

MAX_QUESTION_CHARS = 600


# --------------------------------------------------------------------- map layers


def _parse_json_values(text: str) -> list[Any]:
    """Parse zero or more JSON values written one after another.

    Tools that return a list reach us as several JSON objects in one text block,
    so a plain json.loads would fail on them.
    """
    decoder = json.JSONDecoder()
    values, i = [], 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            value, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        values.append(value)
    return values


def map_layers(tool_calls: list[dict]) -> dict:
    """Turn the agent's tool calls into things to draw: points, lines, circles, polygons."""
    layers: dict[str, list] = {"points": [], "lines": [], "circles": [], "polygons": []}
    seen: set[tuple] = set()

    def add_point(lat: float, lon: float, label: str, kind: str = "result") -> None:
        key = (round(lat, 4), round(lon, 4), label)
        if key not in seen:
            seen.add(key)
            layers["points"].append({"lat": lat, "lon": lon, "label": label, "kind": kind})

    for call in tool_calls:
        name, args = call.get("name"), call.get("arguments") or {}
        result = call.get("result") or ""
        if result.startswith("ERROR") or not isinstance(args, dict):
            continue
        values = _parse_json_values(result)

        if name == "geocode":
            for v in values:
                if isinstance(v, dict) and "lat" in v and "lon" in v:
                    add_point(v["lat"], v["lon"], v.get("name", "place"), "geocoded")

        elif name == "distance_bearing" and values and isinstance(values[0], dict):
            try:
                p1 = [float(args["lat1"]), float(args["lon1"])]
                p2 = [float(args["lat2"]), float(args["lon2"])]
            except (KeyError, TypeError, ValueError):
                continue
            v = values[0]
            label = f"{v.get('distance_km')} km, bearing {v.get('initial_bearing_deg')} deg"
            layers["lines"].append({"from": p1, "to": p2, "label": label})

        elif name in ("nearest_features", "features_within"):
            for v in values:
                if isinstance(v, dict) and "lat" in v and "lon" in v:
                    label = f"{v.get('name', 'place')} ({v.get('distance_km')} km)"
                    add_point(v["lat"], v["lon"], label, "result")
            if name == "features_within":
                try:
                    layers["circles"].append(
                        {"lat": float(args["lat"]), "lon": float(args["lon"]), "radius_km": float(args["radius_km"])}
                    )
                except (KeyError, TypeError, ValueError):
                    pass

        elif name == "point_in_polygon":
            polygon = args.get("polygon_geojson")
            if isinstance(polygon, str):
                try:
                    polygon = json.loads(polygon)
                except json.JSONDecodeError:
                    polygon = None
            inside = bool(values and values[0] is True)
            if isinstance(polygon, dict):
                layers["polygons"].append({"geojson": polygon, "inside": inside})
            try:
                add_point(float(args["lat"]), float(args["lon"]), "inside" if inside else "outside", "inside" if inside else "outside")
            except (KeyError, TypeError, ValueError):
                pass

    return layers


# ------------------------------------------------------------------------ routes


async def index(request: Request) -> HTMLResponse:
    html = resources.files("geoagent").joinpath("static/index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


async def places(request: Request) -> JSONResponse:
    return JSONResponse([p.as_dict() for p in geo.load_places()])


async def models(request: Request) -> JSONResponse:
    """Models the configured server offers, with the default first. Falls back to just the default."""
    default = os.environ.get("GEOAGENT_MODEL", agent.DEFAULT_MODEL)
    base = os.environ.get("GEOAGENT_BASE_URL", agent.DEFAULT_BASE_URL).rstrip("/")
    found: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{base}/models")
            resp.raise_for_status()
            found = [m["id"] for m in resp.json().get("data", [])]
    except Exception:
        pass
    names = [default] + [m for m in found if m != default]
    return JSONResponse({"default": default, "models": names, "server_reachable": bool(found)})


async def ask(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Request body must be JSON."}, status_code=400)
    question = body.get("question") if isinstance(body, dict) else None
    model = body.get("model") if isinstance(body, dict) else None
    if not isinstance(question, str) or not question.strip():
        return JSONResponse({"error": "Please enter a question."}, status_code=400)
    if len(question) > MAX_QUESTION_CHARS:
        return JSONResponse({"error": f"Question is too long (max {MAX_QUESTION_CHARS} characters)."}, status_code=400)
    if model is not None and not isinstance(model, str):
        return JSONResponse({"error": "model must be a string."}, status_code=400)

    try:
        result = await agent.ask_async(question.strip(), model=model or None)
    except httpx.ConnectError:
        base = os.environ.get("GEOAGENT_BASE_URL", agent.DEFAULT_BASE_URL)
        return JSONResponse({"error": f"Could not reach the model server at {base}. Is Ollama running?"}, status_code=502)
    except httpx.HTTPStatusError as exc:
        return JSONResponse({"error": f"The model server returned an error: {exc.response.status_code}."}, status_code=502)
    except Exception as exc:  # keep the UI usable whatever goes wrong inside the agent
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)

    result["layers"] = map_layers(result.get("tool_calls", []))
    return JSONResponse(result)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/places", places),
        Route("/api/models", models),
        Route("/api/ask", ask, methods=["POST"]),
    ]
)


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the GeoAgent web UI.")
    parser.add_argument("--host", default="127.0.0.1", help="default 127.0.0.1 (this computer only)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
