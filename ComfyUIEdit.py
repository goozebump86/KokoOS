# filename: ComfyUIEdit.py (ComfyUI Image Edit Bridge running on Port 3017)
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

app = FastAPI(title="ComfyUI Image Edit MCP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
SERVER_PORT = 3017 
COMFY_ADDR = "127.0.0.1:8188" 
COMFY_OUTPUT_DIR = r"C:\Users\gooze\Documents\ComfyUI\output"

# 🚀 BULLETPROOF PATHS FOR YOUR DOWNLOADS FOLDER 🚀
BASE_KOKO_DIR = r"C:\Users\gooze\Downloads"
WORKFLOW_PATH = r"C:\Users\gooze\Downloads\image_flux2_klein_image_edit_4b_base.json"

MCP_VERSION = "2024-11-05"

async def function_edit_image(image_filename: str, prompt: str) -> str:
    """Injects the source image and prompt into the Flux2 edit workflow."""
    client_id = str(uuid.uuid4())
    logger.info(f"Editing image {image_filename} with prompt: {prompt}")
    
    try:
        if not os.path.exists(WORKFLOW_PATH):
            return f"❌ Workflow file not found at: {WORKFLOW_PATH}"
            
        with open(WORKFLOW_PATH, 'r') as f:
            workflow = json.load(f)

        # 🚀 THE SMART ROUTER: Checks both Telegram AND Generation folders 🚀
        found_path = None
        actual_filename = image_filename
        
        # 1. Check if it's already an absolute path that exists
        if os.path.isabs(image_filename) and os.path.exists(image_filename):
            found_path = image_filename
        else:
            # 2. Look in the Telegram Downloads folder
            path_in_downloads = os.path.join(BASE_KOKO_DIR, image_filename)
            # 3. Look in the ComfyUI Output folder (for freshly generated images)
            path_in_comfy = os.path.join(COMFY_OUTPUT_DIR, os.path.basename(image_filename))

            if os.path.exists(path_in_downloads):
                found_path = path_in_downloads
                logger.info("Image found in Telegram Downloads folder.")
            elif os.path.exists(path_in_comfy):
                found_path = path_in_comfy
                logger.info("Image found in ComfyUI Output folder.")

        if found_path:
            logger.info(f"Uploading local file {found_path} to ComfyUI input folder...")
            with open(found_path, 'rb') as img_file:
                upload_files = {"image": (os.path.basename(found_path), img_file, "application/octet-stream")}
                await asyncio.to_thread(requests.post, f"http://{COMFY_ADDR}/upload/image", files=upload_files)
            actual_filename = os.path.basename(found_path) # ComfyUI only wants the base name now
        else:
            return f"❌ Error: Could not locate '{image_filename}' in the Telegram folder OR the ComfyUI output folder. Make sure the filename is exact."
            
        # 🚀 INJECT VARIABLES INTO THE FLUX2 KLEIN WORKFLOW 🚀
        # Node 76: LoadImage (The source image)
        workflow["76"]["inputs"]["image"] = actual_filename
        # Node 75:74: CLIPTextEncode (The edit prompt)
        workflow["75:74"]["inputs"]["text"] = prompt
        # Node 75:73: RandomNoise (Fresh seed)
        workflow["75:73"]["inputs"]["noise_seed"] = random.randint(1, 10**15)
        
        p = {"prompt": workflow, "client_id": client_id}
        
        # Mark time before starting
        start_time = time.time()
        
        # Fire the prompt to ComfyUI
        res = await asyncio.to_thread(requests.post, f"http://{COMFY_ADDR}/prompt", json=p, timeout=30)
        res.raise_for_status()

        logger.info("Edit prompt sent. Scanning folder for new output...")
        
        # ZERO API POLLING. WATCH THE FOLDER EVERY 1 SECOND.
        latest_file = None
        output_filename = None
        
        for _ in range(120): # Max wait time: 120 seconds for heavy edits
            list_of_files = glob.glob(os.path.join(COMFY_OUTPUT_DIR, '*.png'))
            if list_of_files:
                current_latest = max(list_of_files, key=os.path.getctime)
                
                if os.path.getctime(current_latest) > start_time:
                    latest_file = current_latest
                    output_filename = os.path.basename(latest_file)
                    logger.info(f"BOOM. Found edited image: {output_filename}")
                    break 
                    
            await asyncio.sleep(1)

        if not latest_file:
            return "❌ Timeout error: No edited image appeared in the output folder after 120 seconds."

        await asyncio.sleep(0.5)

        return f"✅ **SUCCESS!** The image was successfully edited and saved as `{output_filename}`.\n\nCRITICAL INSTRUCTION: You must now immediately use the `send_telegram_media` tool to send `{output_filename}` to the user."

    except Exception as e:
        logger.error(f"Failed to edit: {e}")
        return f"❌ An unexpected error occurred: {str(e)}"
        
    finally:
        # ALWAYS flush VRAM
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
                "serverInfo": {"name": "comfyui-edit-mcp", "version": "1.0.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [{
                    "name": "edit_image",
                    "description": "Edits an existing image using ComfyUI. You MUST provide the exact filename of the source image and a descriptive prompt of what to change.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "image_filename": {"type": "string", "description": "The exact filename of the image to edit (e.g., source_image.png)"},
                            "prompt": {"type": "string", "description": "What to change in the image (e.g., 'Make the car red')"}
                        },
                        "required": ["image_filename", "prompt"]
                    }
                }]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "edit_image":
            text_result = await function_edit_image(args.get("image_filename", ""), args.get("prompt", ""))
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
    return HTMLResponse(f"<h3>ComfyUI Image Edit MCP Running on Port {SERVER_PORT}</h3>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)