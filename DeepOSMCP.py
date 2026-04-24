# filename: DeepOSMCP.py (Ghost in the Machine Bridge running on Port 3022)
import os
import asyncio
import logging
import psutil
import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Koko Deep OS Control MCP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SERVER_PORT = 3022
MCP_VERSION = "2024-11-05"

# Critical Windows processes Koko is NOT allowed to kill
PROTECTED_PROCESSES = ["explorer.exe", "svchost.exe", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe", "dwm.exe", "Taskmgr.exe", "python.exe", "llama-server.exe", "cmd.exe", "powershell.exe"]

# --- SYSTEM TOOLS ---

def function_check_system_health() -> str:
    """Returns the current CPU, RAM, and Disk usage of the host machine."""
    cpu_usage = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    
    health_report = (
        f"🖥️ **System Health Report:**\n"
        f"**CPU Usage:** {cpu_usage}%\n"
        f"**RAM Usage:** {ram.percent}% ({ram.used / (1024**3):.2f}GB / {ram.total / (1024**3):.2f}GB)\n"
        f"**C: Drive:** {disk.percent}% full ({disk.free / (1024**3):.2f}GB free)"
    )
    return health_report

def function_list_top_processes(sort_by: str = "memory", limit: int = 10) -> str:
    """Lists the top consuming processes on the machine."""
    process_list = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            process_list.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if sort_by.lower() == "cpu":
        process_list = sorted(process_list, key=lambda p: p['cpu_percent'], reverse=True)
    else:
        process_list = sorted(process_list, key=lambda p: p['memory_percent'], reverse=True)

    report = [f"📊 **Top {limit} Processes (Sorted by {sort_by.upper()}):**"]
    for p in process_list[:limit]:
        report.append(f"PID: {p['pid']} | Name: {p['name']} | CPU: {p['cpu_percent']}% | RAM: {p['memory_percent']:.1f}%")
        
    return "\n".join(report)

def function_kill_process(target: str) -> str:
    """Kills a process by its PID or exact process name."""
    try:
        # Check if target is a PID (number)
        if target.isdigit():
            pid = int(target)
            proc = psutil.Process(pid)
            if proc.name() in PROTECTED_PROCESSES:
                return f"❌ Access Denied: '{proc.name()}' is a protected Windows core process."
            proc_name = proc.name()
            proc.terminate()
            return f"✅ SUCCESS: Terminated process {proc_name} (PID: {pid})."
        
        # Target is a name
        else:
            if target in PROTECTED_PROCESSES:
                return f"❌ Access Denied: '{target}' is a protected Windows core process."
            
            terminated_count = 0
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() == target.lower():
                    psutil.Process(proc.info['pid']).terminate()
                    terminated_count += 1
            
            if terminated_count > 0:
                return f"✅ SUCCESS: Terminated {terminated_count} instance(s) of '{target}'."
            else:
                return f"❌ Could not find any running process named '{target}'."
                
    except psutil.NoSuchProcess:
        return f"❌ Error: Process '{target}' does not exist."
    except psutil.AccessDenied:
        return f"❌ Error: Access denied. Koko requires Administrator privileges to kill '{target}'."
    except Exception as e:
        return f"❌ Error: {str(e)}"

def function_kill_process_by_port(port: int) -> str:
    """Finds and terminates whatever process is running on a specific network port."""
    try:
        killed_pids = []
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    proc_name = proc.name()
                    # We bypass the PROTECTED_PROCESSES check here intentionally, 
                    # because if python.exe is a zombie on a port we NEED it dead.
                    proc.terminate()
                    killed_pids.append(f"{proc_name} (PID: {conn.pid})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        if killed_pids:
            return f"✅ SUCCESS: Freed port {port} by terminating: {', '.join(killed_pids)}"
        else:
            return f"❌ Could not find any active, killable process hogging port {port}."
    except Exception as e:
        return f"❌ Error checking network ports: {str(e)}"

async def function_launch_application(app_name: str) -> str:
    """Uses Windows shell to open standard applications or URIs."""
    try:
        subprocess.Popen(f"start {app_name}", shell=True)
        return f"✅ Command sent to Windows to launch: '{app_name}'"
    except Exception as e:
        return f"❌ Failed to launch '{app_name}': {str(e)}"

# --- MCP RPC LOGIC ---
async def handle_rpc(message: dict) -> dict:
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": MCP_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "koko-deepos-mcp", "version": "1.1.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "check_system_health",
                        "description": "Checks the host machine's current CPU, RAM, and storage drive usage.",
                        "inputSchema": {"type": "object", "properties": {}, "required": []}
                    },
                    {
                        "name": "list_top_processes",
                        "description": "Lists the programs currently using the most system resources. Useful for finding what is slowing the PC down.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "sort_by": {"type": "string", "enum": ["cpu", "memory"], "default": "memory"},
                                "limit": {"type": "integer", "default": 10}
                            }, "required": []
                        }
                    },
                    {
                        "name": "kill_process",
                        "description": "Force closes a hanging or unwanted application. Provide the exact process name (e.g., 'chrome.exe') or PID.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "target": {"type": "string", "description": "The PID number or exact process name (like 'notepad.exe')."}
                            }, "required": ["target"]
                        }
                    },
                    {
                        "name": "kill_process_by_port",
                        "description": "Frees up a network port by finding and terminating the process using it. Use this if a server says 'Address already in use' or 'WinError 10048'.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "port": {"type": "integer", "description": "The port number to free up (e.g., 8090, 3010)."}
                            }, "required": ["port"]
                        }
                    },
                    {
                        "name": "launch_application",
                        "description": "Opens a program on the host PC (e.g., 'notepad', 'calc', 'explorer').",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "app_name": {"type": "string", "description": "The name of the application to run."}
                            }, "required": ["app_name"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "check_system_health":
            result = function_check_system_health()
        elif tool_name == "list_top_processes":
            result = function_list_top_processes(args.get("sort_by", "memory"), args.get("limit", 10))
        elif tool_name == "kill_process":
            result = function_kill_process(args.get("target"))
        elif tool_name == "kill_process_by_port":
            result = function_kill_process_by_port(args.get("port"))
        elif tool_name == "launch_application":
            result = await function_launch_application(args.get("app_name"))
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

@app.get("/")
def read_root(): return HTMLResponse(f"<h3>Koko Deep OS Control Running on Port {SERVER_PORT}</h3>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)