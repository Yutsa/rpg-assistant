#!/usr/bin/env python3
"""Smoke-test the cof-rules MCP server over stdio (newline-delimited JSON-RPC)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/workspace")
DB = ROOT / "data" / "cof_rules.db"
DLL = ROOT / "packages/cof-rules/src/CofRules.Mcp/bin/Debug/net8.0/CofRules.Mcp.dll"
DOTNET = str(Path.home() / ".dotnet" / "dotnet")


def send(proc: subprocess.Popen[bytes], payload: dict) -> None:
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    assert proc.stdin is not None
    proc.stdin.write(line.encode("utf-8"))
    proc.stdin.flush()


def read_json_line(proc: subprocess.Popen[bytes], timeout: float = 20.0) -> dict:
    assert proc.stdout is not None
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        chunk = proc.stdout.read(1)
        if not chunk:
            err = b""
            if proc.stderr:
                err = proc.stderr.read()[-4000:]
            raise RuntimeError(f"EOF from MCP. stderr={err!r} buf={buf!r}")
        buf += chunk
        if buf.endswith(b"\n"):
            line = buf.strip()
            buf = b""
            if not line:
                continue
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
    raise TimeoutError("No JSON-RPC line from MCP server")


def text_of(result: dict) -> str:
    content = result.get("result", {}).get("content") or []
    return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")


def main() -> int:
    env = os.environ.copy()
    env["DOTNET_ROOT"] = str(Path.home() / ".dotnet")
    env["PATH"] = env["DOTNET_ROOT"] + ":" + env.get("PATH", "")
    env["COF_RULES_DB"] = str(DB)
    proc = subprocess.Popen(
        [DOTNET, DLL],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "cof-rules-smoke", "version": "1.0"},
                },
            },
        )
        init = read_json_line(proc)
        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = read_json_line(proc)
        names = sorted(t["name"] for t in tools["result"]["tools"])
        send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "cof_stats", "arguments": {}}})
        stats = json.loads(text_of(read_json_line(proc)))
        send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "cof_get_people", "arguments": {"name": "Nain"}},
            },
        )
        nain = json.loads(text_of(read_json_line(proc)))
        out = {
            "initialize": init.get("result", {}).get("serverInfo"),
            "tools": names,
            "elements": stats.get("elements"),
            "nain": {
                "name": nain.get("name"),
                "kind": nain.get("kind"),
                "page_start": nain.get("page_start"),
            },
        }
        Path("/opt/cursor/artifacts/cof_rules_mcp_smoke.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if "cof_get_people" not in names or stats.get("elements", 0) < 1000 or nain.get("name") != "Nain":
            return 2
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
