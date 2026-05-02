# filename: CoderMCP.py (Senior Dev Bridge running on Port 3020)
# UPDATED: Uses secure config from config.py instead of hardcoded values

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Koko Senior Dev MCP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SERVER_PORT = 3020
MCP_VERSION = "2024-11-05"

# Folders to ignore to prevent context window explosion
IGNORE_DIRS = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build"}

# --- SENIOR DEV TOOLS ---

def function_read_directory_tree(path: str, max_depth: int = 4) -> str:
    """Returns a visual tree map of all files and subfolders in the given path.

    Args:
        path: Absolute or relative path to scan. Defaults to cwd if empty.
        max_depth: Maximum directory depth to traverse (default 4).

    Returns:
        Formatted string representation of the directory tree.
    """
    if not path:
        path = os.getcwd()
        
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        return f"❌ Error: Path does not exist: {target}"
    
    tree_lines = []
    
    def walk_tree(current_path, prefix="", depth=0):
        if depth > max_depth:
            return
            
        try:
            items = sorted(os.listdir(current_path))
        except PermissionError:
            return
            
        # Filter out ignored directories
        items = [item for item in items if item not in IGNORE_DIRS]
        
        for i, item in enumerate(items):
            is_last = (i == len(items) - 1)
            item_path = os.path.join(current_path, item)
            
            connector = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{connector}{item}")
            
            if os.path.isdir(item_path):
                extension = "    " if is_last else "│   "
                walk_tree(item_path, prefix + extension, depth + 1)

    tree_lines.append(f"📁 {os.path.basename(target) or target}")
    walk_tree(target)
    
    result = "\n".join(tree_lines)
    # Failsafe for massive directories
    if len(result) > 10000:
        return result[:10000] + "\n... [Tree truncated due to size]"
    return result

async def function_run_terminal_command(command: str, cwd: Optional[str] = None) -> str:
    """Executes a shell command and returns stdout/stderr output.

    Args:
        command: The command line string to execute.
        cwd: Working directory for the command. Defaults to current working directory.

    Returns:
        Formatted string with success/failure status and command output.
    Raises:
        asyncio.TimeoutError: If command exceeds 60 second timeout (caught internally).
    """
    if not cwd:
        cwd = os.getcwd()
        
    target_dir = os.path.abspath(os.path.expanduser(cwd))
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    logger.info(f"Executing: `{command}` in {target_dir}")
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=target_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            process.kill()
            return f"❌ Error: Command timed out after 60 seconds."

        out_str = stdout.decode(errors='replace').strip()
        err_str = stderr.decode(errors='replace').strip()
        
        if process.returncode == 0:
            output = out_str if out_str else "Command executed successfully with no output."
            if err_str:
                output += f"\n[Warnings/Logs]:\n{err_str}"
            if len(output) > 4000:
                output = output[:4000] + "\n... [Output truncated]"
            return f"✅ SUCCESS (Exit Code 0):\n{output}"
        else:
            error_output = err_str if err_str else out_str
            return f"❌ FAILED (Exit Code {process.returncode}):\n{error_output}"
            
    except Exception as e:
        return f"❌ System Error: {str(e)}"

async def function_git_commit(message: str, cwd: Optional[str] = None) -> str:
    """Stages all changes and commits them to Git with the provided message.

    Args:
        message: Commit message summarizing the changes.
        cwd: Directory containing the .git folder. Defaults to current working directory.

    Returns:
        Formatted string with git add and commit results.
    """
    if not cwd:
        cwd = os.getcwd()
        
    target_dir = os.path.abspath(os.path.expanduser(cwd))
    if not os.path.exists(os.path.join(target_dir, ".git")):
        await function_run_terminal_command("git init", target_dir)
        
    add_result = await function_run_terminal_command("git add .", target_dir)
    if "❌" in add_result:
        return f"Failed to stage files:\n{add_result}"
        
    commit_cmd = f'git commit -m "{message}"'
    commit_result = await function_run_terminal_command(commit_cmd, target_dir)
    return commit_result

async def function_github_publish(repo_name: str, visibility: str, cwd: Optional[str] = None) -> str:
    """Creates a new GitHub repository and pushes the local code to it.

    Args:
        repo_name: Name of the new GitHub repository (no spaces).
        visibility: Repository visibility — 'public' or 'private'. Defaults to 'private' if invalid.
        cwd: Directory containing the .git folder. Defaults to current working directory.

    Returns:
        Formatted string with success/failure status and GitHub CLI output.
    """
    if not cwd:
        cwd = os.getcwd()
        
    target_dir = os.path.abspath(os.path.expanduser(cwd))
    
    if not os.path.exists(os.path.join(target_dir, ".git")):
        return f"❌ Error: No Git repository found in {target_dir}. Please run git_commit first."

    valid_vis = ["public", "private"]
    if visibility.lower() not in valid_vis:
        visibility = "private"

    gh_check = await function_run_terminal_command("gh --version", target_dir)
    if "❌" in gh_check:
        return "❌ Error: GitHub CLI ('gh') is not installed or not in PATH."

    logger.info(f"Publishing to GitHub: {repo_name} as {visibility.lower()}...")

    push_cmd = f'gh repo create {repo_name} --{visibility.lower()} --source=. --remote=origin --push'
    push_result = await function_run_terminal_command(push_cmd, target_dir)
    
    if "✅" in push_result or "Created repository" in push_result:
        return f"✅ SUCCESS: Project pushed to GitHub as a {visibility.lower()} repository!\nDetails:\n{push_result}"
    else:
        return f"❌ GitHub Publish Failed:\n{push_result}"

# --- MCP RPC LOGIC ---
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
                "serverInfo": {"name": "koko-coder-mcp", "version": "1.1.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "read_directory_tree",
                        "description": "Scans a folder and returns a visual tree map of all files and subfolders.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "The absolute or relative path to scan."}
                            }
                        }
                    },
                    {
                        "name": "run_terminal_command",
                        "description": "Executes a shell command (e.g., npm install, pytest, python script.py).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "The command line string to execute."},
                                "cwd": {"type": "string", "description": "The directory to run the command inside."}
                            }, "required": ["command"]
                        }
                    },
                    {
                        "name": "git_commit",
                        "description": "Automatically runs 'git add .' followed by 'git commit -m' with your provided message.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string", "description": "The commit message summarizing the changes."},
                                "cwd": {"type": "string", "description": "The directory containing the .git folder."}
                            }, "required": ["message"]
                        }
                    },
                    {
                        "name": "github_publish",
                        "description": "Creates a new GitHub repository and pushes the local code to it.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "repo_name": {"type": "string", "description": "The name of the new GitHub repository (no spaces)."},
                                "cwd": {"type": "string", "description": "The directory containing the .git folder."},
                                "visibility": {
                                    "type": "string",
                                    "enum": ["public", "private"],
                                    "description": "Whether the repository should be public or private."
                                }
                            }, "required": ["repo_name", "visibility"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        # The Failsafe: If she gets lazy and leaves the directory blank, we fill it in for her.
        safe_cwd = args.get("cwd")
        if not safe_cwd:
            safe_cwd = os.getcwd()
            
        if tool_name == "read_directory_tree":
            result = function_read_directory_tree(args.get("path", safe_cwd))
        elif tool_name == "run_terminal_command":
            result = await function_run_terminal_command(args.get("command"), safe_cwd)
        elif tool_name == "git_commit":
            result = await function_git_commit(args.get("message"), safe_cwd)
        elif tool_name == "github_publish":
            result = await function_github_publish(args.get("repo_name"), args.get("visibility"), safe_cwd)
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}
            
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}}
    elif method == "ping": return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    else: return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

@app.get("/sse")
async def get_sse(request: Request):
    async def event_generator():
        base = str(request.base_url).rstrip('/')
        yield f"event: endpoint\ndata: {base}/messages\n\n"
        while True:
            await asyncio.sleep(15)
            yield ": heartbeat\n\n"
    return StreamingResponse(event_generator(), media_type="text-event-stream")

@app.post("/messages")
@app.post("/sse")
async def post_messages(request: Request):
    try:
        body = await request.json()
        if "id" in body: return JSONResponse(content=await handle_rpc(body))
        return JSONResponse(content={"status": "ok"})
    except Exception as e: return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
