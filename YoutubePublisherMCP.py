# filename: YouTubePublisherMCP.py (Content Factory Bridge running on Port 3019)
import os
import json
import asyncio
import logging
import shutil
import subprocess
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Google API Imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Content Factory MCP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- CONFIGURATION ---
SERVER_PORT = 3019
MCP_VERSION = "2024-11-05"

# Directories to search for media files
COMFY_OUTPUT_DIR = r"C:\Users\gooze\Documents\ComfyUI\output"
BASE_KOKO_DIR = r"C:\Users\gooze\Downloads"
VOICE_SERVER_URL = "http://127.0.0.1:5050/tts"

# YouTube API Configuration
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = os.path.join(BASE_KOKO_DIR, "client_secrets.json")
TOKEN_FILE = os.path.join(BASE_KOKO_DIR, "youtube_token.json")

def find_file(filename: str) -> str:
    if os.path.isabs(filename) and os.path.exists(filename): return filename
    paths_to_check = [
        os.path.join(COMFY_OUTPUT_DIR, os.path.basename(filename)),
        os.path.join(BASE_KOKO_DIR, "downloads", os.path.basename(filename)),
        os.path.join(BASE_KOKO_DIR, os.path.basename(filename))
    ]
    for path in paths_to_check:
        if os.path.exists(path): return path
    return None

# --- AUDIO DURATION HELPER (PATCHED) ---
async def get_audio_duration(ffmpeg_exe, audio_path):
    import re
    process = await asyncio.create_subprocess_exec(ffmpeg_exe, "-i", audio_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    # Fixed Regex to catch all variations of duration formats
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr.decode('utf-8', errors='ignore'))
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 15.0 # default fallback

async def function_generate_voice_file(text: str, output_name: str = "narration.wav") -> str:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(VOICE_SERVER_URL, json={"text": text, "voice": "af_bella"})
            if res.status_code == 200:
                save_path = os.path.join(BASE_KOKO_DIR, "downloads", output_name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f: f.write(res.content)
                return f"✅ Audio saved successfully to `{output_name}` in the downloads folder."
            return f"❌ Voice Server Error: {res.status_code} - {res.text}"
    except Exception as e: return f"❌ Voice connection failed: {e}"

# --- 🚀 UPDATED: SLIDESHOW ENGINE WITH PERFECT TIMING ---
async def function_create_slideshow_short(image_filenames: list, audio_filename: str, output_name: str = "slideshow_short.mp4") -> str:
    """Creates a vertical slideshow video from multiple images, fading between them."""
    if not isinstance(image_filenames, list) or len(image_filenames) == 0:
        return "❌ Error: image_filenames must be a non-empty list of strings."
        
    ffmpeg_exe = os.path.join(BASE_KOKO_DIR, "ffmpeg.exe")
    aud_path = find_file(audio_filename)
    if not aud_path: return f"❌ Error: Could not find audio file: {audio_filename}"
    
    valid_images = []
    for img in image_filenames:
        p = find_file(img)
        if p: valid_images.append(p)
        else: logger.warning(f"Could not find image: {img}")
        
    if not valid_images: return "❌ Error: No valid images found from the provided list."
    
    out_path = os.path.join(COMFY_OUTPUT_DIR, output_name)
    
    audio_duration = await get_audio_duration(ffmpeg_exe, aud_path)
    num_images = len(valid_images)
    
    # Dynamic fade duration based on pacing
    fade_dur = 0.5 if (audio_duration / num_images) <= 2.0 else 1.0 
    
    # MATH FIX: Calculate exact clip length needed so FFmpeg doesn't buffer overflow
    if num_images == 1:
        base_duration = audio_duration
    else:
        base_duration = (audio_duration + (num_images - 1) * fade_dur) / num_images
    
    command = [ffmpeg_exe, "-y", "-i", aud_path] # Input 0
    
    for i, img in enumerate(valid_images):
        # Add 1 extra second to the very last image so it doesn't end a frame early before -shortest kicks in
        clip_dur = base_duration + 1.0 if i == num_images - 1 else base_duration
        command.extend(["-loop", "1", "-framerate", "30", "-t", f"{clip_dur:.3f}", "-i", img])
        
    filter_complex = ""
    for i in range(num_images):
        idx = i + 1 # offset by 1 for audio
        filter_complex += f"[{idx}:v]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:10,scale=1080:1920,setsar=1[bg{i}];"
        filter_complex += f"[{idx}:v]scale=1080:1920:force_original_aspect_ratio=decrease,setsar=1[fg{i}];"
        filter_complex += f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p[v{i}];"
        
    if num_images == 1:
        filter_complex += "[v0]copy[outv]"
    else:
        last_out = "v0"
        for i in range(1, num_images):
            offset = i * (base_duration - fade_dur)
            filter_complex += f"[{last_out}][v{i}]xfade=transition=fade:duration={fade_dur}:offset={offset:.3f}[x{i}];"
            last_out = f"x{i}"
        filter_complex += f"[{last_out}]copy[outv]"
        
    command.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "0:a",
        "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-b:v", "5M",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", out_path
    ])
    
    try:
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode != 0: 
            return f"❌ FFmpeg Error during slideshow generation: {stderr.decode('utf-8', errors='ignore')[-500:]}"
        return f"✅ **SUCCESS!** Slideshow video created as `{output_name}` with {num_images} images."
    except Exception as e:
        return f"❌ Execution Error: {str(e)}"

async def function_apply_advanced_effect(image_filename: str, audio_filename: str, effect_type: str, output_name: str = "advanced_short.mp4") -> str:
    logger.info(f"Applying {effect_type} effect to {image_filename}")
    img_path, aud_path = find_file(image_filename), find_file(audio_filename)
    if not img_path: return f"❌ Error: Could not find image file: {image_filename}"
    if not aud_path: return f"❌ Error: Could not find audio file: {audio_filename}"
    out_path, ffmpeg_exe = os.path.join(COMFY_OUTPUT_DIR, output_name), os.path.join(BASE_KOKO_DIR, "ffmpeg.exe")
    base_scale = "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"

    if effect_type == "visualizer": filter_complex = f"{base_scale}[bg]; [1:a]showwaves=s=1080x400:mode=cline:colors=0x00FFFF@0.8[wave]; [bg][wave]overlay=0:H-h-200[v]"
    elif effect_type == "cinematic": filter_complex = f"{base_scale},noise=alls=8:allf=t+u,vignette=PI/4[v]"
    elif effect_type == "cyberpunk": filter_complex = f"{base_scale},noise=alls=15:allf=t,rgbashift=rh=-4:bh=4,eq=contrast=1.3:saturation=1.5[v]"
    elif effect_type == "breather": filter_complex = "[0:v]scale=2160:3840:force_original_aspect_ratio=decrease,pad=2160:3840:(ow-iw)/2:(oh-ih)/2[hires]; [hires]zoompan=z='min(1.0+in/3000,1.05)':d=3000:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1080x1920:fps=30[v]"
    else: return f"❌ Error: Unknown effect type '{effect_type}'."

    try:
        command = [
            ffmpeg_exe, "-y", "-loop", "1", "-framerate", "30", "-i", img_path, "-i", aud_path,
            "-filter_complex", filter_complex, "-map", "[v]", "-map", "1:a",
            "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-b:v", "5M", 
            "-c:a", "aac", "-b:a", "192k", "-shortest", out_path
        ]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode != 0: return f"❌ FFmpeg Error: {stderr.decode('utf-8', errors='ignore')}"
        return f"✅ **SUCCESS!** Rendered `{output_name}` using the **{effect_type.upper()}** effect!"
    except Exception as e: return f"❌ Error: {str(e)}"

async def function_stitch_video(image_filename: str, audio_filename: str, output_name: str = "final_short.mp4") -> str:
    img_path, aud_path = find_file(image_filename), find_file(audio_filename)
    out_path, ffmpeg_exe = os.path.join(COMFY_OUTPUT_DIR, output_name), os.path.join(BASE_KOKO_DIR, "ffmpeg.exe")
    command = [
        ffmpeg_exe, "-y", "-loop", "1", "-framerate", "30", "-i", img_path, "-i", aud_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-b:v", "5M", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", out_path
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    return f"✅ **SUCCESS!** Video created as `{output_name}`."

async def function_create_blurred_bg_short(image_filename: str, audio_filename: str, output_name: str = "blurred_short.mp4") -> str:
    img_path, aud_path = find_file(image_filename), find_file(audio_filename)
    out_path, ffmpeg_exe = os.path.join(COMFY_OUTPUT_DIR, output_name), os.path.join(BASE_KOKO_DIR, "ffmpeg.exe")
    command = [
        ffmpeg_exe, "-y", "-loop", "1", "-framerate", "30", "-i", img_path, "-i", aud_path,
        "-filter_complex", "[0:v]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=10:10,scale=1080:1920[bg];[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]",
        "-map", "[v]", "-map", "1:a", "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-b:v", "5M", "-c:a", "aac", "-b:a", "192k", "-shortest", out_path
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    return f"✅ **SUCCESS!** Blurred video created as `{output_name}`."

async def function_duck_audio(bgm_filename: str, voice_filename: str, output_name: str = "ducked_audio.m4a") -> str:
    bgm_path, voice_path = find_file(bgm_filename), find_file(voice_filename)
    out_path, ffmpeg_exe = os.path.join(COMFY_OUTPUT_DIR, output_name), os.path.join(BASE_KOKO_DIR, "ffmpeg.exe")
    command = [
        ffmpeg_exe, "-y", "-i", bgm_path, "-i", voice_path,
        "-filter_complex", "[1:a]asplit[sc][v2];[0:a][sc]sidechaincompress=threshold=0.03:ratio=4:level_sc=0.5:release=500[bg];[bg][v2]amix=inputs=2:duration=longest[aout]",
        "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", out_path
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    return f"✅ **SUCCESS!** Audio mixed into `{output_name}`."

async def function_upload_youtube(video_filename: str, title: str, description: str, tags: str, privacy_status: str = "public") -> str:
    video_path = find_file(video_filename)
    if not video_path: return f"❌ Error: Could not find video file: {video_filename}"
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES) if os.path.exists(TOKEN_FILE) else None
    youtube = build("youtube", "v3", credentials=creds)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if "#shorts" not in description.lower(): description += "\n\n#shorts"
    body = {"snippet": {"title": title, "description": description, "tags": tag_list, "categoryId": "22"}, "status": {"privacyStatus": privacy_status.lower()}}
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
    response = await asyncio.to_thread(request.execute)
    return f"✅ **UPLOAD SUCCESSFUL!** Live at: https://youtu.be/{response.get('id')}"

# --- MCP RPC LOGIC ---
async def handle_rpc(message: dict) -> dict:
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": "youtube-publisher-mcp", "version": "2.0.0"}}
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "create_slideshow_short",
                        "description": "Creates a vertical slideshow video from MULTIPLE images, fading between them with a blurred background, synchronized to the audio track.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "image_filenames": {"type": "array", "items": {"type": "string"}, "description": "List of image filenames (e.g., ['img1.png', 'img2.png'])"},
                                "audio_filename": {"type": "string"},
                                "output_name": {"type": "string", "default": "slideshow_short.mp4"}
                            }, "required": ["image_filenames", "audio_filename"]
                        }
                    },
                    {
                        "name": "apply_advanced_video_effect",
                        "description": "Applies a premium, GPU-accelerated visual effect to a static image and audio track. KOKO: Choose 'visualizer' for podcasts/audio-focus, 'cinematic' for history/documentaries, 'cyberpunk' for horror/tech, or 'breather' for a smooth, high-quality slow zoom.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "image_filename": {"type": "string"},
                                "audio_filename": {"type": "string"},
                                "effect_type": {"type": "string", "enum": ["visualizer", "cinematic", "cyberpunk", "breather"]},
                                "output_name": {"type": "string", "default": "advanced_short.mp4"}
                            }, "required": ["image_filename", "audio_filename", "effect_type"]
                        }
                    },
                    {"name": "generate_voice_file", "description": "Converts text to .wav using Kokoro.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "output_name": {"type": "string", "default": "narration.wav"}}, "required": ["text"]}},
                    {"name": "stitch_video", "description": "Basic static fit.", "inputSchema": {"type": "object", "properties": {"image_filename": {"type": "string"}, "audio_filename": {"type": "string"}, "output_name": {"type": "string", "default": "final_short.mp4"}}, "required": ["image_filename", "audio_filename"]}},
                    {"name": "create_blurred_bg_short", "description": "Blurs horizontal images for vertical formats.", "inputSchema": {"type": "object", "properties": {"image_filename": {"type": "string"}, "audio_filename": {"type": "string"}, "output_name": {"type": "string", "default": "blurred_short.mp4"}}, "required": ["image_filename", "audio_filename"]}},
                    {"name": "duck_audio", "description": "Mixes BGM and Voiceover.", "inputSchema": {"type": "object", "properties": {"bgm_filename": {"type": "string"}, "voice_filename": {"type": "string"}, "output_name": {"type": "string", "default": "ducked_audio.m4a"}}, "required": ["bgm_filename", "voice_filename"]}},
                    {"name": "upload_youtube_short", "description": "Uploads to YouTube.", "inputSchema": {"type": "object", "properties": {"video_filename": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "tags": {"type": "string"}, "privacy_status": {"type": "string", "enum": ["public", "private", "unlisted"]}}, "required": ["video_filename", "title", "description", "tags"]}}
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "create_slideshow_short": result = await function_create_slideshow_short(args.get("image_filenames", []), args.get("audio_filename"), args.get("output_name", "slideshow_short.mp4"))
        elif tool_name == "apply_advanced_video_effect": result = await function_apply_advanced_effect(args.get("image_filename"), args.get("audio_filename"), args.get("effect_type"), args.get("output_name", "advanced_short.mp4"))
        elif tool_name == "generate_voice_file": result = await function_generate_voice_file(args.get("text"), args.get("output_name", "narration.wav"))
        elif tool_name == "stitch_video": result = await function_stitch_video(args.get("image_filename"), args.get("audio_filename"), args.get("output_name", "final_short.mp4"))
        elif tool_name == "create_blurred_bg_short": result = await function_create_blurred_bg_short(args.get("image_filename"), args.get("audio_filename"), args.get("output_name", "blurred_short.mp4"))
        elif tool_name == "duck_audio": result = await function_duck_audio(args.get("bgm_filename"), args.get("voice_filename"), args.get("output_name", "ducked_audio.m4a"))
        elif tool_name == "upload_youtube_short": result = await function_upload_youtube(args.get("video_filename"), args.get("title"), args.get("description"), args.get("tags"), args.get("privacy_status", "public"))
        else: return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}
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