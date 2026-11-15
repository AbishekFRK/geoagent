# GeoAgent

An [MCP](https://modelcontextprotocol.io) server that gives LLM agents geospatial tools, plus an eval suite that measures how reliably an agent uses them.

> **Status: v0.2 work in progress.** The tools, the agent loop and the eval cases are real and run. Scoring the agent against the eval cases is the next milestone. See the [roadmap](#roadmap).

## Why

LLMs are bad at geometry from memory. Ask one for the distance between two cities and it will give a confident, slightly wrong number. GeoAgent gives the model real tools for coordinates, distances and proximity, then **measures** whether it picks the right tool and returns the right answer, instead of hoping.

## Tools

| Tool | What it does |
|---|---|
| `geocode` | Look up a place by name or airport code in the bundled dataset |
| `distance_bearing` | Geodesic distance (WGS84) and bearings between two points |
| `features_within` | Places within a radius of a point, nearest first |
| `nearest_features` | The N nearest places to a point |
| `point_in_polygon` | Point-in-polygon test against a GeoJSON polygon |

Plus one **resource** (`geoagent://catalog`, the dataset) and one **prompt** (`geo_question`, instructions for using the tools carefully).

Planned for v0.2: `elevation_profile` from an open DEM, and a larger dataset (Natural Earth / OpenStreetMap).

## Quick start

```bash
git clone <this repo>
cd geoagent
python -m venv .venv
.venv\Scripts\activate          # Windows. On macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Run the server and try the tools in the MCP inspector:

```bash
npx @modelcontextprotocol/inspector geoagent-server
```

Use it from Claude Desktop or Claude Code by adding it as a stdio server:

```json
{
  "mcpServers": {
    "geoagent": { "command": "geoagent-server" }
  }
}
```

## Ask it a question (no API key needed)

The bundled agent talks to any tool-calling model through the OpenAI-compatible chat API. By default it uses a local [Ollama](https://ollama.com) model, so it is free and private:

```bash
ollama pull qwen2.5:14b
python -m geoagent.agent -v "How far is Chennai from Bengaluru, in km?"
```

`-v` prints every tool call. Pick another model with `--model llama3.1:8b`. To use a hosted provider instead, set `GEOAGENT_BASE_URL`, `GEOAGENT_MODEL` and `GEOAGENT_API_KEY`.

## Architecture

```
User question
     |
     v
  Agent (any tool-calling LLM)   src/geoagent/agent.py
     |  MCP (stdio)
     v
GeoAgent MCP server  (src/geoagent/server.py)
     |
     v
Pure geo functions   (src/geoagent/geo.py: pyproj, shapely)
     |
     v
Bundled sample dataset (src/geoagent/data/sample_places.csv)
```

The server uses the MCP Python SDK 2.x (`MCPServer`, called `FastMCP` in 1.x). The geospatial logic lives in plain functions in `geo.py` with no MCP dependency, so it is unit-tested directly. `server.py` only wraps them.

## Evals

`evals/cases.jsonl` holds questions with objective ground truth (distances computed independently, known nearest airports, deliberate "ambiguous question" cases). The runner will report two numbers:

- **Tool selection accuracy**: did the agent call the right tools?
- **Answer accuracy**: is the final answer within tolerance of the ground truth?

Results table: _to be added after milestone 4._

## Roadmap

- [x] Repo, packaging, 5 tools, resource, prompt, unit tests
- [x] First eval cases and schema checks
- [x] Agent loop (`agent.py`), model-agnostic, tested with a scripted fake model and a real local model
- [ ] Eval runner and published results, compared across models (e.g. `qwen2.5:14b` vs `llama3.1:8b`)
- [ ] `elevation_profile` and a larger open dataset
- [ ] Demo gif and tagged release

## Data

The bundled `sample_places.csv` is a small hand-made set of Indian cities and airports with approximate coordinates, for demos and tests only. Do not use it for navigation. Larger open datasets are planned.

## License

MIT
