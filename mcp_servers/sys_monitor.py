"""System Monitor MCP Server — Real-time system resource monitoring.

Provides a FastAPI-based MCP server that reports CPU, RAM, and disk usage
statistics via psutil. Supports JSON-RPC 2.0 tool calls and SSE streaming
connections for real-time monitoring.

Tools:
    get_system_stats: Returns CPU, RAM, and disk usage statistics.

Version: 1.2.0
"""

import json
import time
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
import psutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SystemMonitor MCP")
SERVER_PORT = 3055
MCP_VERSION = "2024-11-05"

sse_clients: list = []


def get_system_stats() -> Dict[str, Any]:
    """Collect and return real-time system resource statistics.

    Retrieves CPU usage percentage, virtual memory (total/used/available) in GB,
    memory usage percentage, and disk C: drive (total/used/free) in GB with usage percentage.

    Returns:
        Dictionary containing CPU, RAM, and disk metrics in human-readable format.
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')

    return {
        "cpu_usage_percent": cpu_percent,
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_available_gb": round(mem.available / (1024**3), 2),
        "ram_usage_percent": mem.percent,
        "disk_c_total_gb": round(disk.total / (1024**3), 2),
        "disk_c_used_gb": round(disk.used / (1024**3), 2),
        "disk_c_free_gb": round(disk.free / (1024**3), 2),
        "disk_c_usage_percent": disk.percent
    }


# --- MCP JSON-RPC 2.0 HANDLER ---

async def handle_rpc(message: dict) -> dict:
    """Routes incoming MCP JSON-RPC messages to the appropriate tool handler.

    Supports methods: initialize, tools/list, tools/call, and ping.
    Returns standardized JSON-RPC 2.0 responses with proper error codes.

    Args:
        message: JSON-RPC message dict containing id, method, and params.

    Returns:
        JSON-RPC response dict with result or error payload.
    """
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": MCP_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "system-monitor-mcp", "version": "1.2.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "get_system_stats",
                        "description": "Returns real-time CPU, RAM, and disk C: usage statistics.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "get_system_stats":
            try:
                result = get_system_stats()
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                }
            except Exception as e:
                logger.error(f"get_system_stats failed: {e}")
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Internal error: {str(e)}"}}
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}


# --- ENDPOINTS ---

@app.get("/sse")
async def sse_endpoint(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time system monitoring.

    Establishes a persistent connection that keeps the client alive.
    Clients can poll /messages for tool execution results.

    Args:
        request: The incoming HTTP request.

    Returns:
        StreamingResponse with SSE data format including welcome message and heartbeat.
    """
    async def generate():
        client_id = str(time.time())
        sse_clients.append({'id': client_id, 'closed': False})
        yield f"data: {json.dumps({'type': 'welcome', 'client_id': client_id})}\n\n"
        try:
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"SSE client {client_id} disconnected: {e}")
        finally:
            sse_clients[:] = [c for c in sse_clients if c['id'] != client_id]

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/")
async def read_root() -> HTMLResponse:
    """Health check endpoint — returns server status and version info.

    Returns:
        HTML response with server name, version, uptime indicator, and available tools list.
    """
    return HTMLResponse(
        content=(
            f"<h2>SystemMonitor MCP</h2>"
            f"<p>Version: 1.2.0</p>"
            f"<p>Status: Online</p>"
            f"<p>Port: {SERVER_PORT}</p>"
            f"<p>Tools: get_system_stats</p>"
        )
    )


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint for the SystemMonitor MCP service.

    Returns:
        Status dictionary indicating service health.
    """
    return {"status": "ok", "service": "SystemMonitor MCP"}


@app.post("/messages")
async def post_messages(request: Request) -> JSONResponse:
    """Handle JSON-RPC 2.0 tool calls.

    Accepts tool execution requests and routes them to the appropriate handler.
    Returns results in JSON-RPC 2.0 format.

    Args:
        request: The incoming HTTP request containing JSON-RPC payload.

    Returns:
        JSONResponse with tool execution result in JSON-RPC 2.0 format.
    """
    try:
        body = await request.json()
        if "id" in body:
            return JSONResponse(content=await handle_rpc(body))
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Messages endpoint error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
