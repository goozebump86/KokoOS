# filename: ComfyUIimage.py (ComfyUI Bridge running on Port 3011)
import json
import uuid
import random
import asyncio
import requests
import logging
import os
import glob
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ComfyUIimage Generation MCP (True Folder Polling)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
SERVER_PORT = 3011 
COMFY_ADDR = "127.0.0.1:8188" 
COMFY_OUTPUT_DIR = r"C:\Users\gooze\Documents\ComfyUI\output"
WORKFLOW_PATH = r"C:\Users\gooze\June-ai\mcp_servers\image_z_image_turbo_api.json"
MCP_VERSION = "2024-11-05"

async def function_generate_image(prompt: str) -> str:
    """Bypasses API completely. Watches the hard drive for the new file."""
    client_id = str(uuid.uuid4())
    logger.info(f"Generating image for prompt: {prompt}")
    
    try:
        if not os.path.exists(WORKFLOW_PATH):
            return f"❌ Workflow file not found at: {WORKFLOW_PATH}"
            
        with open(WORKFLOW_PATH, 'r') as f:
            workflow = json.load(f)
            
        workflow["57:27"]["inputs"]["text"] = prompt
        workflow["57:3"]["inputs"]["seed"] = random.randint(1, 10**15)
        
        p = {"prompt": workflow, "client_id": client_id}
        
        # 1. Mark the exact time BEFORE we ask ComfyUI to start
        start_time = time.time()
        
        # Fire the prompt
        res = await asyncio.to_thread(requests.post, f"http://{COMFY_ADDR}/prompt", json=p, timeout=30)
        res.raise_for_status()

        logger.info("Prompt sent. Ignoring API. Scanning folder for new files...")
        
        # 2. ZERO API POLLING. JUST WATCH THE FOLDER EVERY 1 SECOND.
        latest_file = None
        image_filename = None
        
        for _ in range(60): # Max wait time: 60 seconds
            list_of_files = glob.glob(os.path.join(COMFY_OUTPUT_DIR, '*.png'))
            if list_of_files:
                # Find the newest file in the folder
                current_latest = max(list_of_files, key=os.path.getctime)
                
                # If the file was created AFTER we hit "Go", it's our image!
                if os.path.getctime(current_latest) > start_time:
                    latest_file = current_latest
                    image_filename = os.path.basename(latest_file)
                    logger.info(f"BOOM. Found new image: {image_filename}")
                    break 
                    
            await asyncio.sleep(1)

        if not latest_file:
            return "❌ Timeout error: No new image appeared in the output folder after 60 seconds."

        # Wait 0.5 seconds just to make sure ComfyUI finished writing the bytes to the disk
        await asyncio.sleep(0.5)
        
        # 3. Read the bytes directly from the hard drive
        with open(latest_file, 'rb') as f:
            image_bytes = f.read()

        # Silently upload a copy to ComfyUI's 'input' folder so the 3D node can see it
        upload_files = {"image": (image_filename, image_bytes, "image/png")}
        await asyncio.to_thread(requests.post, f"http://{COMFY_ADDR}/upload/image", files=upload_files)

        # 🚀 THE FIX: NO MORE MASSIVE BASE64 STRINGS 🚀
        # We just hand the filename back to Koko so she doesn't crash, and tell her to send it.
        return f"✅ **SUCCESS!** The image was created and saved as `{image_filename}`.\n\nCRITICAL INSTRUCTION: You must now immediately use the `send_telegram_media` tool to send `{image_filename}` to the user."

    except Exception as e:
        logger.error(f"Failed to generate: {e}")
        return f"❌ An unexpected error occurred: {str(e)}"
        
    finally:
        # ALWAYS flush VRAM, even if it crashed
        try:
            await asyncio.to_thread(requests.post, f"http://{COMFY_ADDR}/free", json={"unload_models": True, "free_memory": True}, timeout=5)
            logger.info("ComfyUI VRAM flushed successfully.")
        except Exception as e:
            logger.warning(f"Failed to flush ComfyUI VRAM: {e}")

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
                "serverInfo": {"name": "comfyui-mcp-hardened", "version": "1.1.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [{
                    "name": "generate_image",
                    "description": "Generates an image using ComfyUI. Provide a highly detailed visual prompt.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"prompt": {"type": "string"}},
                        "required": ["prompt"]
                    }
                }]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "generate_image":
            text_result = await function_generate_image(args.get("prompt", ""))
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": text_result}]}
            }
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}
    
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

# --- HTTP/SSE ROUTES ---
@app.get("/sse")
async def get_sse(request: Request):
    async def event_generator():
        base = str(request.base_url).rstrip('/')
        yield f"event: endpoint\ndata: {base}/messages\n\n"
        while True:
            await asyncio.sleep(15)
            yield ": heartbeat\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

@app.post("/messages")
@app.post("/sse")
async def post_messages(request: Request):
    try:
        body = await request.json()
        if "id" in body:
            result = await handle_rpc(body)
            return JSONResponse(content=result)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/")
def read_root():
    return HTMLResponse(f"<h3>ComfyUI MCP (True Folder Polling) Running on Port {SERVER_PORT}</h3>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)