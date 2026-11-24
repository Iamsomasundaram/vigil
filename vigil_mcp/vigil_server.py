"""F8: MCP-style tool server exposing NVD and EPSS helpers.

This module offers two layers:
1) Simple in-process discovery/invocation functions used by tests and L4 fallback.
2) Optional stdio MCP server runner when the `mcp` package is installed.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "fetch_nvd_data",
            "description": "Fetch live NVD data for a CVE.",
            "input_schema": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"],
                "additionalProperties": False,
            },
            "source": "mcp",
        },
        {
            "name": "fetch_epss_score",
            "description": "Fetch EPSS score for a CVE.",
            "input_schema": {
                "type": "object",
                "properties": {"cve_id": {"type": "string"}},
                "required": ["cve_id"],
                "additionalProperties": False,
            },
            "source": "mcp",
        },
    ]


async def _fetch_nvd_data(cve_id: str) -> dict[str, Any]:
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            vulns = data.get("vulnerabilities", [])
            if not vulns:
                return {"error": f"CVE {cve_id} not found in NVD"}
            cve = vulns[0]["cve"]
            desc = next((d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"), "N/A")
            metrics = cve.get("metrics", {})
            score = None
            sev = None
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if key in metrics:
                    m = metrics[key][0].get("cvssData", {})
                    score = m.get("baseScore")
                    sev = m.get("baseSeverity") or metrics[key][0].get("baseSeverity")
                    break
            return {
                "source": "NVD",
                "cve_id": cve_id,
                "description": desc,
                "cvss_score": score,
                "severity": sev,
            }
        except Exception as e:
            return {"error": f"NVD API call failed: {e}"}


async def _fetch_epss_score(cve_id: str) -> dict[str, Any]:
    url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            rows = data.get("data", [])
            if not rows:
                return {"source": "EPSS", "cve_id": cve_id, "score": None, "percentile": None}
            row = rows[0]
            return {
                "source": "EPSS",
                "cve_id": cve_id,
                "score": float(row.get("epss", 0)),
                "percentile": float(row.get("percentile", 0)),
            }
        except Exception as e:
            return {"error": f"EPSS API call failed: {e}"}


async def call_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "fetch_nvd_data":
        return json.dumps(await _fetch_nvd_data(str(arguments.get("cve_id", ""))))
    if name == "fetch_epss_score":
        return json.dumps(await _fetch_epss_score(str(arguments.get("cve_id", ""))))
    return json.dumps({"error": f"Unknown tool: {name}"})


async def run_stdio_server() -> None:
    """Optional MCP stdio server if the `mcp` package is available."""
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("mcp package is required to run stdio server") from exc

    app = FastMCP("vigil-tools")

    @app.tool()
    async def fetch_nvd_data(cve_id: str) -> dict[str, Any]:
        return await _fetch_nvd_data(cve_id)

    @app.tool()
    async def fetch_epss_score(cve_id: str) -> dict[str, Any]:
        return await _fetch_epss_score(cve_id)

    await app.run_stdio_async()


def main() -> None:
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
