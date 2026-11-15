"""Agent loop: connects any tool-calling LLM to the GeoAgent MCP server.

The model side speaks the OpenAI-compatible chat-completions API, so it works with
a local Ollama server (default, free, no account), and with any hosted provider
that offers the same API (Groq, OpenRouter, Gemini's compatibility endpoint, etc.).

    python -m geoagent.agent "How far is Chennai from Bengaluru?"
    python -m geoagent.agent --model llama3.1:8b "Which airport is nearest Mysuru?"

Environment variables (all optional):
    GEOAGENT_BASE_URL   default http://localhost:11434/v1  (Ollama)
    GEOAGENT_MODEL      default qwen2.5:14b
    GEOAGENT_API_KEY    only needed for hosted providers
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:14b"
MAX_STEPS = 6


def _server_params() -> StdioServerParameters:
    # Launch the server with the same interpreter, so it works from any virtualenv.
    return StdioServerParameters(command=sys.executable, args=["-m", "geoagent.server"])


def _to_openai_tool(tool: Any) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def _result_text(result: Any) -> str:
    parts = [getattr(c, "text", "") for c in result.content]
    text = "\n".join(p for p in parts if p)
    return f"ERROR: {text}" if getattr(result, "is_error", False) else text


def _parse_arguments(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    return json.loads(raw)


async def ask_async(
    question: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    max_steps: int = MAX_STEPS,
) -> dict:
    """Answer a geospatial question. Returns {"answer", "tool_calls", "steps", "model"}.

    `transport` lets tests replace the network with a scripted fake model.
    """
    model = model or os.environ.get("GEOAGENT_MODEL", DEFAULT_MODEL)
    base_url = (base_url or os.environ.get("GEOAGENT_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
    api_key = api_key or os.environ.get("GEOAGENT_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    tool_calls: list[dict] = []
    async with (
        stdio_client(_server_params()) as (read, write),
        ClientSession(read, write) as session,
        httpx.AsyncClient(base_url=base_url, headers=headers, timeout=300, transport=transport) as http,
    ):
        await session.initialize()
        tools = [_to_openai_tool(t) for t in (await session.list_tools()).tools]

        # The server ships its own instructions as an MCP prompt; use them as the user turn.
        prompt = await session.get_prompt("geo_question", {"question": question})
        messages: list[dict] = [{"role": "user", "content": prompt.messages[0].content.text}]

        for step in range(1, max_steps + 1):
            resp = await http.post(
                "/chat/completions",
                json={"model": model, "messages": messages, "tools": tools, "temperature": 0},
            )
            resp.raise_for_status()
            message = resp.json()["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            if not calls:
                return {
                    "answer": (message.get("content") or "").strip(),
                    "tool_calls": tool_calls,
                    "steps": step,
                    "model": model,
                }

            messages.append(message)
            for call in calls:
                fn = call["function"]
                try:
                    args = _parse_arguments(fn.get("arguments"))
                    text = _result_text(await session.call_tool(fn["name"], args))
                except Exception as exc:  # bad JSON or a tool failure goes back to the model
                    args, text = fn.get("arguments"), f"ERROR: {exc}"
                tool_calls.append({"name": fn["name"], "arguments": args, "result": text})
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": text})

    return {
        "answer": "",
        "tool_calls": tool_calls,
        "steps": max_steps,
        "model": model,
        "error": f"No final answer after {max_steps} steps.",
    }


def ask(question: str, **kwargs: Any) -> dict:
    """Synchronous wrapper around ask_async."""
    return asyncio.run(ask_async(question, **kwargs))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the GeoAgent a geospatial question.")
    parser.add_argument("question")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("-v", "--verbose", action="store_true", help="show each tool call")
    args = parser.parse_args()

    result = ask(args.question, model=args.model, base_url=args.base_url)
    if args.verbose:
        for c in result["tool_calls"]:
            print(f"[tool] {c['name']}({json.dumps(c['arguments'])}) -> {c['result']}")
    print(result["answer"] or result.get("error", "(no answer)"))


if __name__ == "__main__":
    main()
