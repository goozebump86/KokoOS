# filename: ComfyUIAudio.py (ComfyUI Audio Generation Bridge running on Port 3018)
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

app = FastAPI(title="ComfyUI Audio Generation MCP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
SERVER_PORT = 3018 
COMFY_ADDR = "127.0.0.1:8188" 
COMFY_OUTPUT_DIR = r"C:\Users\gooze\Documents\ComfyUI\output"

WORKFLOW_PATH = r"C:\Users\gooze\Downloads\audio_ace_step1_5_xl_turbo.json"

MCP_VERSION = "2024-11-05"

async def function_generate_audio(
    tags: str, 
    lyrics: str, 
    duration: int = 120, 
    bpm: int = 120, 
    keyscale: str = "E minor", 
    language: str = "en", 
    seed: int = -1, 
    temperature: float = 0.85, 
    top_p: float = 0.9, 
    top_k: int = 0
) -> str:
    """Injects the tags, lyrics, and parameters into the Ace 1.5 XL Turbo Audio workflow."""
    client_id = str(uuid.uuid4())
    
    # Handle the seed (if -1 or 0 is passed, generate a random one)
    actual_seed = seed if seed > 0 else random.randint(1, 10**15)
    
    logger.info(f"Generating audio. Tags: {tags} | Duration: {duration}s | BPM: {bpm} | Key: {keyscale} | Lang: {language} | Seed: {actual_seed}")
    
    try:
        if not os.path.exists(WORKFLOW_PATH):
            return f"❌ Workflow file not found at: {WORKFLOW_PATH}"
            
        with open(WORKFLOW_PATH, 'r') as f:
            workflow = json.load(f)

        # 🚀 DYNAMIC NODE FINDERS 🚀
        # Automatically locate the Primitive nodes for duration and seed no matter what their IDs are
        duration_node_id = None
        seed_node_id = None
        
        for node_id, node_data in workflow.items():
            title = node_data.get("_meta", {}).get("title", "")
            class_type = node_data.get("class_type", "")
            
            if class_type == "PrimitiveFloat" or "Duration" in title:
                duration_node_id = node_id
            elif class_type == "PrimitiveInt" or "Seed" in title:
                seed_node_id = node_id

        # 🚀 INJECT VARIABLES INTO THE XL TURBO WORKFLOW 🚀
        
        # Node 107: SaveAudioMP3
        if "107" in workflow:
            workflow["107"]["inputs"]["filename_prefix"] = "ace_xl_audio"

        # Inject Seed dynamically
        if seed_node_id and seed_node_id in workflow:
            workflow[seed_node_id]["inputs"]["value"] = actual_seed

        # Inject Duration dynamically into the Primitive Float node
        if duration_node_id and duration_node_id in workflow:
            workflow[duration_node_id]["inputs"]["value"] = float(duration)
        else:
            # Fallback if the primitive nodes are ever removed
            if "98" in workflow: workflow["98"]["inputs"]["seconds"] = float(duration)
            if "94" in workflow: workflow["94"]["inputs"]["duration"] = float(duration)

        # Node 94: TextEncodeAceStepAudio1.5
        if "94" in workflow:
            workflow["94"]["inputs"]["tags"] = tags
            workflow["94"]["inputs"]["lyrics"] = lyrics
            workflow["94"]["inputs"]["bpm"] = bpm
            workflow["94"]["inputs"]["keyscale"] = keyscale
            workflow["94"]["inputs"]["language"] = language
            workflow["94"]["inputs"]["temperature"] = temperature
            workflow["94"]["inputs"]["top_p"] = top_p
            workflow["94"]["inputs"]["top_k"] = top_k
        
        p = {"prompt": workflow, "client_id": client_id}
        
        # Mark time before starting
        start_time = time.time()
        
        # Fire the prompt to ComfyUI
        res = await asyncio.to_thread(requests.post, f"http://{COMFY_ADDR}/prompt", json=p, timeout=30)
        res.raise_for_status()

        logger.info("XL Turbo Audio prompt sent. Scanning folder for new MP3 output... (This may take a few minutes)")
        
        # ZERO API POLLING. WATCH THE FOLDER EVERY 5 SECONDS.
        latest_file = None
        output_filename = None
        
        for _ in range(120): 
            list_of_files = glob.glob(os.path.join(COMFY_OUTPUT_DIR, '*.mp3'))
            if list_of_files:
                current_latest = max(list_of_files, key=os.path.getctime)
                
                # If the file was created AFTER we hit "Go", it's our new song!
                if os.path.getctime(current_latest) > start_time:
                    latest_file = current_latest
                    output_filename = os.path.basename(latest_file)
                    logger.info(f"BOOM. Found generated audio: {output_filename}")
                    break 
                    
            await asyncio.sleep(5)

        if not latest_file:
            return "❌ Timeout error: No generated audio appeared in the output folder after 10 minutes."

        await asyncio.sleep(1.0) # Buffer to ensure file is fully written to disk

        return f"✅ **SUCCESS!** The song was successfully generated and saved as `{output_filename}`.\n\nCRITICAL INSTRUCTION: You must now immediately use the `send_telegram_media` tool to send `{output_filename}` to the user. Do NOT attempt to convert it to base64."

    except Exception as e:
        logger.error(f"Failed to generate audio: {e}")
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
                "serverInfo": {"name": "comfyui-audio-mcp", "version": "1.1.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [{
                    "name": "generate_audio",
                    "description": "Writes and generates a full music track using ComfyUI Ace 1.5 XL Turbo. Provide the style tags, lyrics, and optional tuning parameters.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "tags": {
                                "type": "string", 
                                "description": "The musical style, genre, instruments, and vocal type (e.g., 'pop, upbeat, female vocals, synthwave, heavy bass')"
                            },
                            "lyrics": {
                                "type": "string", 
                                "description": "The actual lyrics of the song, formatted cleanly with [Verse], [Chorus], and [Bridge] tags."
                            },
                            "duration": {
                                "type": "integer",
                                "description": "Length of the song in seconds. Default is 120."
                            },
                            "bpm": {
                                "type": "integer",
                                "description": "Beats per minute (tempo) for the song. Default is 120."
                            },
                            "keyscale": {
                                "type": "string",
                                "description": "Musical key and scale (e.g., 'C major', 'E minor'). Default is 'E minor'."
                            },
                            "language": {
                                "type": "string",
                                "description": "Language code for the vocals (e.g., 'en', 'ja', 'zh'). Default is 'en'."
                            },
                            "seed": {
                                "type": "integer",
                                "description": "Specific seed for the generation. Leave blank or set to -1 for random."
                            },
                            "temperature": {
                                "type": "number",
                                "description": "Sampling temperature (e.g., 0.85). Higher is more creative, lower is more predictable. Default is 0.85."
                            },
                            "top_p": {
                                "type": "number",
                                "description": "Nucleus sampling probability (0.0 to 1.0). Default is 0.9."
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Top-K sampling value. Default is 0."
                            }
                        },
                        "required": ["tags", "lyrics"]
                    }
                }]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "generate_audio":
            text_result = await function_generate_audio(
                tags=args.get("tags", ""),
                lyrics=args.get("lyrics", ""),
                duration=args.get("duration", 120),
                bpm=args.get("bpm", 120),
                keyscale=args.get("keyscale", "E minor"),
                language=args.get("language", "en"),
                seed=args.get("seed", -1),
                temperature=args.get("temperature", 0.85),
                top_p=args.get("top_p", 0.9),
                top_k=args.get("top_k", 0)
            )
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
    return StreamingResponse(event_generator(), media_type="text-event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

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
    return HTMLResponse(f"<h3>ComfyUI Audio Gen MCP (XL Turbo) Running on Port {SERVER_PORT}</h3>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)