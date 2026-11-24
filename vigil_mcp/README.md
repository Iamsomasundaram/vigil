# MCP Tools (F8)

Vigil can expose its NVD + EPSS tools as an MCP stdio server, and consume them
through an in-process MCP client path (F22).

## Run the server

```bash
pip install -e ".[mcp]"
python -m vigil_mcp.vigil_server
```

If the `mcp` package is not installed, `python -m vigil_mcp.vigil_server` exits with a clear error.

## Use tools from L4

Set:

```bash
VIGIL_TOOL_SOURCE=mcp
```

Then call the normal L4 analysis path (`/l4/analyse`) and the tool menu can be sourced from MCP discovery.

For quick inspection of discovered tools:

```bash
GET /l4/tools?source=mcp
```

## MCP client path (F22)

`vigil_mcp/vigil_client.py` discovers and invokes the server tools and runs a
Claude-style tool loop:

```bash
POST /mcp/tool-loop   # body: {"cve_id": "CVE-2021-44228"}
```
