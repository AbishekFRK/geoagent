"""Agent loop that connects Claude to the GeoAgent MCP server.

Milestone 3 (days 7-9). Not implemented yet.

Plan:
  1. Launch `geoagent-server` over stdio with the MCP client from the `mcp` package.
  2. List its tools and pass them to the Anthropic Messages API as tool definitions.
  3. Loop: send the question, run any tool_use blocks through the MCP session,
     return the tool_result blocks, stop when the model answers in plain text.
  4. Return the final answer plus the ordered list of tool calls, so the eval
     runner can score tool selection as well as the answer.

Install the extra first:  pip install -e ".[agent]"
"""

from __future__ import annotations


def ask(question: str) -> dict:
    """Answer a geospatial question. Returns {"answer": str, "tool_calls": [...]}."""
    raise NotImplementedError("Agent loop is planned for milestone 3.")
