"""
MnemOS MCP Server
-----------------
Connects MnemOS to Claude Desktop via Model Context Protocol.

Claude Desktop config (~/.config/claude/claude_desktop_config.json):
{
  "mcpServers": {
    "mnemos": {
      "command": "/path/to/myenv/bin/python",
      "args": ["/path/to/MnemOS/integrations/mcp_server.py"],
      "env": {
        "MNEMOS_URL": "http://localhost:8765",
        "MNEMOS_USER_ID": "default"
      }
    }
  }
}
"""

import os
import sys
import json
import requests
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

BASE_URL = os.getenv("MNEMOS_URL", "http://localhost:8765")
USER_ID  = os.getenv("MNEMOS_USER_ID", "default")
APP_ID   = "claude-desktop"

server = Server("mnemos")


# ─── TOOL DEFINITIONS ─────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name        = "remember",
            description = "Save a memory to MnemOS. Use this when the user shares something important about themselves, their preferences, or facts worth remembering.",
            inputSchema = {
                "type": "object",
                "properties": {
                    "content": {
                        "type":        "string",
                        "description": "The memory to save (1-2 sentences)"
                    },
                    "type": {
                        "type":        "string",
                        "enum":        ["semantic", "episodic", "procedural"],
                        "description": "semantic=fact, episodic=event, procedural=how-to",
                        "default":     "semantic"
                    },
                    "tags": {
                        "type":        "array",
                        "items":       {"type": "string"},
                        "description": "Optional tags for categorization",
                        "default":     []
                    }
                },
                "required": ["content"]
            }
        ),

        types.Tool(
            name        = "recall",
            description = "Search for relevant memories from MnemOS. Use this at the start of a conversation or when the user asks about something you might have remembered.",
            inputSchema = {
                "type": "object",
                "properties": {
                    "query": {
                        "type":        "string",
                        "description": "What to search for in memory"
                    },
                    "limit": {
                        "type":        "integer",
                        "description": "Max number of memories to return",
                        "default":     5
                    }
                },
                "required": ["query"]
            }
        ),

        types.Tool(
            name        = "forget",
            description = "Delete a specific memory by its ID.",
            inputSchema = {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type":        "string",
                        "description": "The ID of the memory to delete"
                    }
                },
                "required": ["memory_id"]
            }
        ),

        types.Tool(
            name        = "list_memories",
            description = "List all stored memories for the current user.",
            inputSchema = {
                "type":       "object",
                "properties": {
                    "limit": {
                        "type":    "integer",
                        "default": 20
                    }
                }
            }
        ),
    ]


# ─── TOOL HANDLERS ────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "remember":
        try:
            resp = requests.post(
                f"{BASE_URL}/memory/store",
                json={
                    "content":  arguments["content"],
                    "type":     arguments.get("type", "semantic"),
                    "tags":     arguments.get("tags", []),
                    "app_id":   APP_ID,
                    "user_id":  USER_ID,
                },
                timeout=10
            )
            data = resp.json()
            return [types.TextContent(
                type = "text",
                text = f"Memory saved (id: {data['id']})"
            )]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error saving memory: {e}")]

    if name == "recall":
        try:
            resp = requests.post(
                f"{BASE_URL}/memory/retrieve",
                json={
                    "query":   arguments["query"],
                    "limit":   arguments.get("limit", 5),
                    "app_id":  APP_ID,
                    "user_id": USER_ID,
                },
                timeout=10
            )
            memories = resp.json().get("memories", [])
            if not memories:
                return [types.TextContent(type="text", text="No relevant memories found.")]
            lines = [f"Found {len(memories)} memories:\n"]
            for i, m in enumerate(memories, 1):
                lines.append(f"{i}. [{m['type']}] {m['content']}")
                lines.append(f"   relevance: {m['relevance']} | id: {m['id']}\n")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error retrieving memories: {e}")]

    if name == "forget":
        try:
            memory_id = arguments["memory_id"]
            requests.delete(f"{BASE_URL}/memory/{memory_id}", timeout=5)
            return [types.TextContent(type="text", text=f"Memory {memory_id} deleted.")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error deleting memory: {e}")]

    if name == "list_memories":
        try:
            limit = arguments.get("limit", 20)
            resp  = requests.get(
                f"{BASE_URL}/memory/all",
                params={"user_id": USER_ID, "limit": limit},
                timeout=10
            )
            memories = resp.json().get("memories", [])
            if not memories:
                return [types.TextContent(type="text", text="No memories stored yet.")]
            lines = [f"Total: {len(memories)} memories\n"]
            for m in memories:
                lines.append(f"• [{m['type']}] {m['content'][:80]}")
                lines.append(f"  id: {m['id']} | app: {m['app_id']}\n")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error listing memories: {e}")]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ─── RUN ──────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
