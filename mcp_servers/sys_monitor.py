import json
import time
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import psutil

app = FastAPI()

sse_clients = []

def call_tool(name, args):
    if name == "get_system_stats":
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
    else:
        return {"error": f"Unknown tool: {name}"}

@app.get("/sse")
async def sse_endpoint(request: Request):
    async def generate():
        client_id = str(time.time())
        sse_clients.append({'id': client_id, 'closed': False})
        yield f"data: {json.dumps({'type': 'welcome', 'client_id': client_id})}\n\n"
        try:
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            pass
        finally:
            sse_clients[:] = [c for c in sse_clients if c['id'] != client_id]

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/messages")
async def messages(request: Request):
    body = await request.json()
    
    if body.get("method") == "tools/call":
        tool_name = body.get("params", {}).get("name", "")
        tool_args = body.get("params", {}).get("arguments", {})
        result = call_tool(tool_name, tool_args)
        
        response = {
            "id": body.get("id", 0),
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}]
            }
        }
        return JSONResponse(content=response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3055)