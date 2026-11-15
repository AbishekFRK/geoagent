import json

import httpx

from geoagent import agent


def scripted_model(replies):
    """A fake OpenAI-compatible endpoint that returns the given messages in order."""
    seen_requests = []
    queue = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": queue.pop(0)}]})

    return httpx.MockTransport(handler), seen_requests


def tool_call(name, arguments, call_id="call_1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}
        ],
    }


def test_agent_runs_a_tool_through_the_real_mcp_server_and_returns_the_answer():
    transport, requests = scripted_model(
        [
            tool_call("distance_bearing", {"lat1": 12.9716, "lon1": 77.5946, "lat2": 13.0827, "lon2": 80.2707}),
            {"role": "assistant", "content": "About 290.5 km."},
        ]
    )
    result = agent.ask("How far is Chennai from Bengaluru?", model="fake", transport=transport)

    assert result["answer"] == "About 290.5 km."
    assert [c["name"] for c in result["tool_calls"]] == ["distance_bearing"]
    assert json.loads(result["tool_calls"][0]["result"])["distance_km"] == 290.543
    assert result["steps"] == 2

    # The model was offered all five tools, and the tool result was sent back to it.
    first, second = requests
    assert {t["function"]["name"] for t in first["tools"]} == {
        "geocode", "distance_bearing", "features_within", "nearest_features", "point_in_polygon",
    }
    assert second["messages"][-1]["role"] == "tool"
    assert "290.543" in second["messages"][-1]["content"]


def test_tool_errors_are_returned_to_the_model_instead_of_crashing():
    transport, requests = scripted_model(
        [
            tool_call("distance_bearing", {"lat1": 95, "lon1": 0, "lat2": 0, "lon2": 0}),
            {"role": "assistant", "content": "That latitude is invalid."},
        ]
    )
    result = agent.ask("Bad input", model="fake", transport=transport)
    assert result["tool_calls"][0]["result"].startswith("ERROR")
    assert result["answer"] == "That latitude is invalid."


def test_gives_up_after_max_steps():
    transport, _ = scripted_model([tool_call("geocode", {"place": "Chennai"}, f"c{i}") for i in range(3)])
    result = agent.ask("loop forever", model="fake", transport=transport, max_steps=3)
    assert result["answer"] == ""
    assert "No final answer" in result["error"]
    assert len(result["tool_calls"]) == 3
