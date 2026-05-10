# 🤝 Contributing to Koko OS

Thank you for your interest in contributing to Koko OS! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style & Standards](#code-style--standards)
- [Adding a New MCP Server](#adding-a-new-mcp-server)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git installed and in PATH
- NVIDIA GPU (8GB+ VRAM) recommended for ComfyUI features
- Basic familiarity with the Model Context Protocol (MCP)

### Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/KokoOS.git
cd KokoOS

# 2. Create virtual environment
python -m venv .venv
# Windows:     .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
copy .env.example .env        # Windows
cp .env.example .env          # Linux/macOS

# 5. Configure your .env with actual credentials
```

---

## Development Workflow

### Branch Naming Convention

```
feature/add-whisper-tts       # New features
fix/fix-memory-leak           # Bug fixes
docs/update-readme            # Documentation changes
refactor/clean-mcp-code       # Code refactoring
test/add-unit-tests           # Test additions
```

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

Examples:
feat(mcp): add voice synthesis endpoint
fix(hermes): resolve cron job timeout
docs(readme): update installation instructions
refactor(outlookmcp): add type hints and docstrings
test(memory): add unit tests for semantic_search
chore(deps): update fastapi to 0.109.0
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

---

## Code Style & Standards

### Python Coding Standards

All Python code must follow these rules:

1. **Type Hints Required** — All function parameters and return types must be annotated:

```python
# ✅ Good
async def search_memories(query: Optional[str] = None, n_results: Optional[int] = 3) -> str:
    """Search the memory database for matching concepts.
    
    Args:
        query: The search query string.
        n_results: Maximum results to return.
        
    Returns:
        Formatted string of matching memories.
    """

# ❌ Bad
def search(query, n=3):  # No type hints, no docstring
```

2. **Google-Style Docstrings** — Every function MUST have a docstring:

```python
def function_name(param1: str, param2: Optional[int] = None) -> bool:
    """One-line summary of what the function does.

    Longer description if needed (2+ lines). Explain complex logic,
    edge cases, or important behavior.

    Args:
        param1: Description of first parameter.
        param2: Description of optional second parameter with default.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.
        ConnectionError: When the MCP server is unreachable.

    Example:
        >>> result = function_name("test", 5)
        >>> result
        True
    """
```

3. **Naming Conventions**
   - Functions/variables: `snake_case`
   - Classes: `PascalCase`
   - Constants: `UPPER_SNAKE_CASE`
   - MCP tool functions: `function_<tool_name>` (e.g., `function_store_memory`)
   - Private methods: `_private_method`

4. **Error Handling** — Never use bare `except:`:

```python
# ✅ Good
try:
    result = await client.post(url, json=data)
except httpx.ConnectTimeout as e:
    logger.error(f"Connection timeout: {e}")
    return "Error: Server unreachable. Please try again."
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return f"Error: {str(e)}"

# ❌ Bad
try:
    result = client.post(url)
except:
    pass  # Silently swallows all errors!
```

5. **Logging** — Use the `logging` module, not `print()`:

```python
logger.info("Server started on port %d", PORT)
logger.warning("MCP server %s is offline", url)
logger.error("Failed to execute tool: %s", error)
```

### MCP Server Requirements

Every MCP server must include:

1. **FastAPI** with proper CORS middleware
2. **SSE and POST endpoints** (`/sse`, `/messages`)
3. **RPC handler** supporting: `initialize`, `tools/list`, `tools/call`, `ping`
4. **Docstrings and type hints** on ALL functions
5. **Error handling** — Never crash the server on bad input
6. **Graceful shutdown** — Close async resources in lifespan

### Example MCP Server Template

See `MemoryMCP.py` for the reference implementation template:

```python
import asyncio
import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Your Server Name")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SERVER_PORT = 9999
MCP_VERSION = "2024-11-05"

# --- YOUR TOOLS HERE ---

def function_example_tool(param: Optional[str] = None) -> str:
    """Description of what this tool does.
    
    Args:
        param: Description of parameter.
        
    Returns:
        Result string.
    """
    try:
        # Tool logic here
        return f"Success: {param}"
    except Exception as e:
        return f"Error: {str(e)}"

async def handle_rpc(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP RPC requests."""
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": MCP_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "your-server-name", "version": "1.0.0"}
        }}
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "tools": [{
                "name": "example_tool",
                "description": "What this tool does",
                "inputSchema": {
                    "type": "object",
                    "properties": {"param": {"type": "string", "description": "Description"}},
                    "required": ["param"]
                }
            }]
        }}
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "example_tool":
            result = function_example_tool(args.get("param"))
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}
            
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}}
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

@app.get("/sse")
async def get_sse(request: Request) -> StreamingResponse:
    """SSE endpoint for streaming connection endpoints."""
    async def event_generator():
        base = str(request.base_url).rstrip('/')
        yield f"event: endpoint\ndata: {base}/messages\n\n"
        while True:
            await asyncio.sleep(15)
            yield ": heartbeat\n\n"
    return StreamingResponse(event_generator(), media_type="text-event-stream")

@app.post("/messages")
async def post_messages(request: Request) -> JSONResponse:
    """Handle incoming MCP tool calls."""
    try:
        body = await request.json()
        if "id" in body:
            return JSONResponse(content=await handle_rpc(body))
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
```

---

## Adding a New MCP Server

### Step-by-Step Guide

1. **Choose an available port** — Check `README.md` for the current port table. Pick one that's not listed.

2. **Create the server file** — Use the template above or copy from an existing server like `MemoryMCP.py`.

3. **Implement your tools** — Each tool should:
   - Have a descriptive name
   - Accept `Optional` parameters with sensible defaults
   - Return a string result (success message or error description)
   - Include comprehensive docstrings

4. **Update the port table** in `README.md`

5. **Add to `boot_koko.bat`** so it starts automatically:
   ```batch
   start /b python YourNewMCP.py
   ```

6. **Test locally**:
   ```bash
   python YourNewMCP.py  # Start the server
   curl -X POST http://localhost:YOUR_PORT/messages \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```

7. **Submit a pull request** with your changes.

---

## Testing

### Manual Testing Checklist

Every new feature or server must pass:

- [ ] Server starts without errors
- [ ] `/messages` endpoint responds to `tools/list`
- [ ] Each tool accepts valid input and returns expected output
- [ ] Each tool handles bad/missing input gracefully (no crashes)
- [ ] SSE endpoint streams correctly
- [ ] No sensitive data leaks in logs or responses

### Quick Test Command

```bash
# Test any MCP server's tools/list endpoint
curl -X POST http://localhost:PORT/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python -m json.tool
```

---

## Documentation

### README.md Updates

When adding or modifying features, update the corresponding section in `README.md`:

- New MCP server → Update the port table and startup commands
- New shell command → Add to the commands table
- New keyboard shortcut → Add to the shortcuts table
- Changed architecture → Update the architecture diagram
- Updated requirements → Update the system requirements table

### Inline Comments

- Comment **why**, not **what** — Assume readers can read code
- Use `# TODO(username):` for planned work
- Use `# FIXME:` for known bugs that need fixing
- Keep comments under 80 characters when possible

---

## Pull Request Process

### Before Submitting

1. **Rebase on latest master** — Ensure your branch is up to date:
   ```bash
   git fetch origin
   git rebase origin/master
   ```

2. **Run a final quality check**:
   - All new code has type hints and docstrings? ✅
   - No hardcoded secrets in any file? ✅
   - README.md updated for any changes? ✅
   - Server starts without errors? ✅

3. **Write a clear PR description**:
   ```markdown
   ## What
   Added a new MCP server for calendar integration.
   
   ## Why
   Users requested calendar access to schedule meetings and events.
   
   ## Changes
   - Created CalendarMCP.py on port 3040
   - Added 3 tools: list_events, create_event, delete_event
   - Updated README.md port table
   - Updated boot_koko.bat
   
   ## Testing
   - [x] Server starts clean
   - [x] All 3 tools tested with valid/invalid input
   - [x] No crashes on bad input
   ```

### Review Process

1. Koko (or the maintainer) will review the PR
2. Automated checks run: type hints, docstrings, security scan
3. Feedback is provided via PR comments
4. Once approved, the PR is merged to master

### Post-Merge

After merging:
- Update `MEMORY.md` with key changes
- Update version number if applicable
- Tag the release

---

## 📬 Need Help?

- Open an Issue on GitHub
- Telegram: [@YourKokoBot](https://t.me/YourKokoBot)
- Check existing issues and PRs for similar work

---

<div align="center">

**Thank you for helping make Koko OS better!** 🌴

</div>
