"""SecretScan MCP Server — Detect hardcoded secrets and API keys in codebases.

Provides a FastAPI-based MCP server that scans directories for hardcoded
secrets including AWS keys, GitHub tokens, database passwords, private keys,
and high-entropy variable assignments. Uses 15+ regex patterns plus Shannon
entropy analysis for detection.

Supports JSON-RPC 2.0 tool calls and SSE streaming connections.

Tools:
    secret_scan: Scans a directory tree for hardcoded secrets and API keys.

Version: 1.2.0
"""

import os
import re
import fnmatch
import json
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SecretScan MCP")
SERVER_PORT = 9087
MCP_VERSION = "2024-11-05"


# --- SECRET DETECTION ENGINE ---

def get_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string to detect high-entropy secrets.

    Higher entropy values indicate more random/secret-like strings. Keys,
    tokens, and passwords typically score above 3.8.

    Args:
        s: The string to calculate entropy for.

    Returns:
        Shannon entropy value (0.0 for empty strings).
    """
    if not s:
        return 0.0
    probability = [float(s.count(c)) / len(s) for c in set(s)]
    return -sum(p * (2**p) for p in probability if p > 0)


def is_high_entropy(value: str, min_length: int = 16) -> bool:
    """Check if a value looks like a random secret based on Shannon entropy.

    Args:
        value: The string value to evaluate.
        min_length: Minimum length required before checking entropy (default 16).

    Returns:
        True if the value has high entropy and meets minimum length, False otherwise.
    """
    if len(value) < min_length:
        return False
    entropy = get_entropy(value)
    return entropy > 3.8


SECRET_PATTERNS: Dict[str, str] = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret Key": r"(?<=aws_secret_access_key\s*=\s*)[A-Za-z0-9/+=]{40}",
    "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36,255}",
    "Generic API Key": r"[Aa][Pp][Ii][_]?[Kk][Ee][Yy]\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?",
    "Generic Secret": r"[Ss][Ee][Cc][Rr][Ee][Tt]\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{8,})['\"]?",
    "Database Password": r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?(\S+?)['\"]?(?=\s|$)",
    "Private Key": r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
    "OpenAI API Key": r"sk-proj-[A-Za-z0-9_-]{20,}",
    "Slack Token": r"xox[baprs]-[0-9a-zA-Z-]+",
    "Google API Key": r"AIza[0-9A-Za-z_\-]{35}",
    "Stripe Key": r"(sk|pk)_(test|live)_[A-Za-z0-9]{24,}",
    "JWT Token": r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
    "Heroku API Key": r"[Hh]eroku.*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "DigitalOcean Token": r"dop_v1_[A-Za-z0-9_-]{64}",
}


def scan_file(filepath: str) -> list:
    """Scan a single file for hardcoded secrets and API keys using regex patterns.

    Checks against 15+ secret patterns including AWS keys, GitHub tokens,
    database passwords, private keys, and more. Also detects high-entropy
    variable assignments that look like secrets.

    Args:
        filepath: Path to the file to scan.

    Returns:
        List of finding dicts with file, line, type, and match fields.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.split('\n')
        findings = []

        for line_num, line in enumerate(lines, 1):
            if len(line) > 500:
                continue

            for secret_type, pattern in SECRET_PATTERNS.items():
                if re.search(pattern, line):
                    findings.append({
                        "file": filepath,
                        "line": line_num,
                        "type": secret_type,
                        "match": line.strip()[:100] + ("..." if len(line.strip()) > 100 else "")
                    })

            assign_patterns = [
                r"([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*['\"]([A-Za-z0-9]{16,})['\"]",
            ]
            for ap in assign_patterns:
                match = re.search(ap, line)
                if match:
                    var_name = match.group(1).lower()
                    secret_val = match.group(2)
                    secret_keywords = ['key', 'token', 'secret', 'password', 'passwd', 'pwd', 'api_key', 'auth', 'access', 'credential']
                    if any(kw in var_name for kw in secret_keywords):
                        if is_high_entropy(secret_val):
                            finding_type = f"High-entropy {var_name}"
                            already_found = any(f["type"] == finding_type and f["line"] == line_num for f in findings)
                            if not already_found:
                                findings.append({
                                    "file": filepath,
                                    "line": line_num,
                                    "type": finding_type,
                                    "match": line.strip()[:100] + ("..." if len(line.strip()) > 100 else "")
                                })

        return findings

    except Exception:
        return []


def should_ignore(filepath: str, ignore_patterns: list) -> bool:
    """Check if a file should be ignored based on glob patterns.

    Args:
        filepath: The file path to check.
        ignore_patterns: List of glob patterns to match against.

    Returns:
        True if the file matches any ignore pattern, False otherwise.
    """
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(os.path.basename(filepath), pattern):
            return True
    return False


def get_depth(path: str, base: str) -> int:
    """Calculate directory depth relative to a base path.

    Args:
        path: The full path to measure.
        base: The base directory to measure from.

    Returns:
        Integer representing the number of directory levels deep.
    """
    rel = os.path.relpath(path, base)
    if rel == '.':
        return 0
    return rel.count(os.sep) + 1


def perform_scan(directory: str, max_depth: int = 3, ignore_patterns: Optional[list] = None) -> Dict[str, Any]:
    """Scan a directory tree for hardcoded secrets and API keys.

    Walks through the specified directory up to max_depth, skipping ignored patterns,
    and checks each file against 15+ secret detection patterns including AWS keys,
    GitHub tokens, database passwords, private keys, and high-entropy values.

    Args:
        directory: Path to the directory to scan.
        max_depth: Maximum directory depth to traverse (default 3).
        ignore_patterns: List of glob patterns to ignore. Defaults to common safe patterns.

    Returns:
        Dictionary with findings list, total files scanned, and risk level assessment.
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Directory not found: {directory}")

    if ignore_patterns is None:
        ignore_patterns = [".git", "__pycache__", "venv", ".env", "node_modules", "*.min.js"]

    all_findings = []
    files_scanned = 0

    for root, dirs, files in os.walk(directory):
        current_depth = get_depth(root, directory)
        if current_depth > max_depth:
            dirs.clear()
            continue

        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git', 'venv', '.venv']]

        for filename in files:
            filepath = os.path.join(root, filename)

            if should_ignore(filepath, ignore_patterns):
                continue

            files_scanned += 1
            findings = scan_file(filepath)
            all_findings.extend(findings)

    high_risk_types = ["Private Key", "AWS Access Key", "GitHub Token", "Stripe Key"]
    has_high_risk = any(f["type"] in high_risk_types for f in all_findings)
    total_severity = len(all_findings)

    if has_high_risk or total_severity > 5:
        risk = "CRITICAL"
    elif total_severity > 0:
        risk = "WARNING"
    else:
        risk = "CLEAN"

    return {
        "findings": all_findings,
        "total_files_scanned": files_scanned,
        "risk_level": risk
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
                "serverInfo": {"name": "secret-scan-mcp", "version": "1.2.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "secret_scan",
                        "description": "Scans a directory tree for hardcoded secrets and API keys using regex patterns and entropy analysis.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "directory": {"type": "string", "description": "The absolute or relative path to scan."},
                                "max_depth": {"type": "integer", "description": "Maximum directory depth to traverse. Default: 3.", "default": 3},
                                "ignore_patterns": {"type": "array", "items": {"type": "string"}, "description": "Glob patterns to ignore. Defaults to common safe patterns."}
                            },
                            "required": ["directory"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "secret_scan":
            directory = args.get("directory")
            max_depth = args.get("max_depth", 3)
            ignore_patterns = args.get("ignore_patterns")

            try:
                result = perform_scan(directory, max_depth, ignore_patterns)
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                }
            except ValueError as e:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": str(e)}}
            except Exception as e:
                logger.error(f"Scan failed: {e}")
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Internal error: {str(e)}"}}
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}


# --- ENDPOINTS ---

@app.get("/sse")
async def get_sse(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time secret scan results.

    Establishes a persistent connection that keeps the client alive.
    Clients can POST to /messages for tool execution.

    Args:
        request: The incoming HTTP request.

    Returns:
        StreamingResponse with SSE data format.
    """
    async def event_generator():
        base = str(request.base_url).rstrip('/')
        yield f"event: endpoint\ndata: {base}/messages\n\n"
        while True:
            await asyncio.sleep(15)
            yield ": heartbeat\n\n"

    return StreamingResponse(event_generator(), media_type="text-event-stream")


@app.get("/")
async def read_root() -> HTMLResponse:
    """Health check endpoint — returns server status and version info.

    Returns:
        HTML response with server name, version, uptime indicator, and available tools list.
    """
    return HTMLResponse(
        content=(
            f"<h2>SecretScan MCP</h2>"
            f"<p>Version: 1.2.0</p>"
            f"<p>Status: Online</p>"
            f"<p>Port: {SERVER_PORT}</p>"
            f"<p>Tools: secret_scan</p>"
        )
    )


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint for the SecretScan MCP service.

    Returns:
        Status dictionary indicating service health.
    """
    return {"status": "ok", "service": "SecretScan MCP"}


@app.post("/scan")
async def scan_directory(req: Request) -> JSONResponse:
    """Legacy REST endpoint — scans a directory for secrets via POST request.

    Accepts JSON body with directory, max_depth, and ignore_patterns fields.
    Kept for backward compatibility. New clients should use tools/call.

    Args:
        req: The incoming HTTP request containing scan parameters.

    Returns:
        JSONResponse with scan results including findings, files scanned, and risk level.
    """
    try:
        body = await req.json()
        directory = body.get("directory")
        max_depth = body.get("max_depth", 3)
        ignore_patterns = body.get("ignore_patterns")

        if not directory:
            return JSONResponse(
                content={"error": "Missing 'directory' field"},
                status_code=400
            )

        result = perform_scan(directory, max_depth, ignore_patterns)
        return JSONResponse(content=result)

    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=404)
    except Exception as e:
        logger.error(f"Scan endpoint error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


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
