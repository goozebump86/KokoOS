# filename: WebBrowserMCP.py
import asyncio
import json
import logging
import sys
import os
import urllib.parse
import urllib.request
import markdown
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright, Browser, BrowserContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- STATE MANAGEMENT ---
browser: Optional[Browser] = None
playwright_context: Optional[BrowserContext] = None
BASE_KOKO_DIR = r"C:\Users\gooze\Downloads"

# --- CONSTANTS ---
SERVER_PORT = 3008
MCP_VERSION = "2024-11-05"

# 🚀 CHROME SPOOFING HEADERS ---
CHROME_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# 🚀 NATIVE STEALTH PAYLOAD 🚀
STEALTH_JS = """
// 1. Hide webdriver
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
// 2. Mock Chrome objects
window.chrome = { runtime: {} };
// 3. Spoof Plugins to look like a real desktop
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
// 4. Spoof Languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
// 5. Spoof Hardware Cores
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    global browser, playwright_context
    logger.info("Initializing Lean Web Scraper (Headless + Native Stealth)...")
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True, 
            args=['--disable-blink-features=AutomationControlled', '--disable-infobars']
        )
        playwright_context = await browser.new_context(
            user_agent=CHROME_USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US'
        )
        await playwright_context.add_init_script(STEALTH_JS)
        logger.info("Lean Scraper engine ready. Single-model mode active.")
    except Exception as e:
        logger.error(f"Failed to start Playwright: {e}")
    yield
    if browser:
        await browser.close()

app = FastAPI(title="Loc.Ai.lly Lean Web Scraper MCP", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- EXISTING TOOLS ---
async def function_web_search(query: str, max_results: int = 5) -> str:
    global playwright_context
    page = await playwright_context.new_page()
    try:
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://search.yahoo.com/search?p={encoded_query}"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000) 
        
        results = await page.evaluate(f"""
            () => {{
                let items = Array.from(document.querySelectorAll('.algo'));
                if (items.length > 0) {{
                    return items.slice(0, {max_results}).map(el => ({{
                        title: el.querySelector('h3') ? el.querySelector('h3').innerText.trim() : 'No Title',
                        href: el.querySelector('a') ? el.querySelector('a').href : 'No URL',
                        body: el.querySelector('.compText, .fz-ms') ? el.querySelector('.compText, .fz-ms').innerText.trim() : 'No Summary'
                    }}));
                }}
                
                items = Array.from(document.querySelectorAll('li.b_algo'));
                if (items.length > 0) {{
                    return items.slice(0, {max_results}).map(el => ({{
                        title: el.querySelector('h2') ? el.querySelector('h2').innerText.trim() : 'No Title',
                        href: el.querySelector('a') ? el.querySelector('a').href : 'No URL',
                        body: el.querySelector('.b_caption p, .b_algoSlug') ? el.querySelector('.b_caption p, .b_algoSlug').innerText.trim() : 'No Summary'
                    }}));
                }}
                
                const allLinks = Array.from(document.querySelectorAll('a'))
                    .filter(a => a.href && a.href.startsWith('http') && !a.href.includes('yahoo.com') && !a.href.includes('bing.com'))
                    .filter(a => a.innerText.trim().length > 20);
                    
                if (allLinks.length > 0) {{
                    return allLinks.slice(0, {max_results}).map(a => ({{
                        title: a.innerText.trim(),
                        href: a.href,
                        body: (a.parentElement ? a.parentElement.innerText.substring(0, 150) : "Relevant link found.") + "..."
                    }}));
                }}
                return null;
            }}
        """)
        
        if not results:
            page_text = await page.evaluate("document.body.innerText.substring(0, 300)")
            return f"❌ Search blocked. The engine served this page instead: '{page_text}'. DO NOT RETRY. Stop and ask the user to clarify."
            
        formatted_results = []
        source_pills = []
        for i, res in enumerate(results):
            formatted_results.append(f"[{i+1}] {res['title']}\nURL: {res['href']}\nSummary: {res['body']}\n")
            source_pills.append(f"{res['title']}::: {res['href']}")
            
        pills_str = "\n".join(source_pills)
        source_block = f"===SOURCES_START===\n{pills_str}\n===SOURCES_END==="
        return f"=== WEB SEARCH RESULTS ===\n" + "\n".join(formatted_results) + f"\n\n{source_block}"
    except Exception as e:
        return f"❌ Search failed: {str(e)}. DO NOT RETRY THE SEARCH."
    finally:
        await page.close()

async def function_get_directions(origin: str, destination: str) -> str:
    try:
        def geocode(place):
            safe_place = urllib.parse.quote(place)
            url = f"https://nominatim.openstreetmap.org/search?q={safe_place}&format=json&limit=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'JuneAI-Local-Assistant'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if not data: return None
                return f"{data[0]['lon']},{data[0]['lat']}"

        coords_orig = await asyncio.to_thread(geocode, origin)
        coords_dest = await asyncio.to_thread(geocode, destination)
        if not coords_orig or not coords_dest: return "❌ Could not find GPS coordinates."

        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{coords_orig};{coords_dest}?overview=false"
        def get_route():
            with urllib.request.urlopen(osrm_url) as response:
                return json.loads(response.read().decode())
        route_data = await asyncio.to_thread(get_route)
        if route_data.get('code') != 'Ok': return "❌ Route calculation failed."

        distance_miles = round((route_data['routes'][0]['distance'] / 1609.34), 1)
        duration_minutes = round(route_data['routes'][0]['duration'] / 60)
        google_maps_link = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin)}&destination={urllib.parse.quote(destination)}&travelmode=driving"

        return f"=== ROUTE CALCULATED ===\n**From:** {origin}\n**To:** {destination}\n**Distance:** {distance_miles} miles\n**Estimated Drive Time:** {duration_minutes} minutes\n[Open Route in Google Maps]({google_maps_link})"
    except Exception as e:
        return f"❌ Maps Error: {str(e)}"

async def function_get_weather(location: str) -> str:
    try:
        safe_loc = urllib.parse.quote(location)
        geo_url = f"https://nominatim.openstreetmap.org/search?q={safe_loc}&format=json&limit=1"
        req = urllib.request.Request(geo_url, headers={'User-Agent': 'LocAilly-Assistant'})
        with urllib.request.urlopen(req) as response:
            geo_data = json.loads(response.read().decode())
            if not geo_data: return f"❌ Could not find location: {location}"
            lat, lon = geo_data[0]['lat'], geo_data[0]['lon']
            display_name = geo_data[0]['display_name'].split(',')[0]

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=auto"
        with urllib.request.urlopen(weather_url) as response:
            w_data = json.loads(response.read().decode())

        daily = w_data['daily']
        forecast = [{"date": daily['time'][i], "max": round(daily['temperature_2m_max'][i]), "min": round(daily['temperature_2m_min'][i]), "code": daily['weather_code'][i]} for i in range(7)]
        result = {"location": display_name, "forecast": forecast}
        return f"=== WEATHER DATA RETRIEVED ===\nYou MUST pass this exact JSON block to the user wrapped in <weather_payload> tags so the UI can draw the widget:\n<weather_payload>\n{json.dumps(result)}\n</weather_payload>\nDo not write the weather out in text, just output the payload."
    except Exception as e:
        return f"❌ Weather API Error: {str(e)}"

async def function_web_fetch(url: str, timeout: int = 30000) -> str:
    if not url.startswith(('http://', 'https://')): url = 'https://' + url
    page = await playwright_context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        await page.wait_for_timeout(1500)
        title = await page.title()
        content = await page.evaluate("""
            () => {
                const clone = document.cloneNode(true);
                clone.querySelectorAll('script, style, nav, footer, header, aside, .sidebar, .comments').forEach(el => el.remove());
                return clone.body ? clone.body.innerText : '';
            }
        """)
        clean_text = " ".join(content.split())
        return f"=== SCRAPED PAGE DATA: {title} ===\n\n{clean_text[:12000]}"
    except Exception as e:
        return f"Failed to fetch page: {str(e)}"
    finally:
        await page.close()

# 🚀 THE NEW OSINT PUBLISHER TOOL 🚀
async def function_generate_intelligence_dossier(target_company: str, markdown_content: str) -> str:
    """Converts Koko's LLM analysis into a premium HTML deliverable."""
    try:
        html_body = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code'])
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Intelligence Dossier: {target_company}</title>
            <style>
                body {{
                    background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 40px;
                }}
                h1, h2, h3 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
                h1 {{ font-size: 2.5em; text-transform: uppercase; letter-spacing: 2px; color: #7ee787; }}
                .header-box {{
                    border: 2px solid #30363d; padding: 20px; border-radius: 8px; margin-bottom: 30px;
                    background-color: #161b22; box-shadow: 0 4px 15px rgba(0,0,0,0.5);
                }}
                .confidential {{ color: #ff7b72; font-weight: bold; font-family: monospace; letter-spacing: 1px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ border: 1px solid #30363d; padding: 12px; text-align: left; }}
                th {{ background-color: #21262d; color: #58a6ff; }}
                blockquote {{ border-left: 4px solid #8b949e; margin: 0; padding-left: 20px; color: #8b949e; font-style: italic; }}
            </style>
        </head>
        <body>
            <div class="header-box">
                <div class="confidential">>> CLASSIFIED INTELLIGENCE DOSSIER</div>
                <h1>{target_company}</h1>
                <p><strong>Generated by:</strong> KOKO Deep Recon Engine</p>
                <p><strong>Status:</strong> Validated & Compiled</p>
            </div>
            <div class="content">
                {html_body}
            </div>
        </body>
        </html>
        """
        
        safe_name = target_company.replace(" ", "_").replace("/", "")
        file_path = os.path.join(BASE_KOKO_DIR, f"DOSSIER_{safe_name}.html")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_template)
            
        return f"✅ **SUCCESS!** Premium Intelligence Dossier compiled and saved to `{file_path}`. You can now open this in your browser and print to PDF!"
    except Exception as e:
        return f"❌ Dossier Generation Error: {str(e)}"

# --- MCP TOOL HANDLERS ---
async def handle_rpc(message: dict) -> dict:
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": "chrome-lean-scraper", "version": "2.1"}}
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {"name": "web_search", "description": "Searches the web for current information and returns a list of links.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 5}}, "required": ["query"]}},
                    {"name": "web_fetch", "description": "Browse a URL, bypass bot protections, and extract the text content.", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "timeout": {"type": "integer", "default": 30000}}, "required": ["url"]}},
                    {"name": "get_directions", "description": "Calculates driving distance and time between two locations.", "inputSchema": {"type": "object", "properties": {"origin": {"type": "string"}, "destination": {"type": "string"}}, "required": ["origin", "destination"]}},
                    {"name": "get_weather", "description": "Gets the 7-day weather forecast.", "inputSchema": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}},
                    {
                        "name": "generate_intelligence_dossier",
                        "description": "Takes Koko's formatted Markdown analysis from her OSINT web scrapes and compiles it into a beautiful HTML dossier ready for the client.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "target_company": {"type": "string"},
                                "markdown_content": {"type": "string", "description": "The full intelligence report written in Markdown."}
                            }, "required": ["target_company", "markdown_content"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        try:
            if tool_name == "web_search": result = await function_web_search(args.get("query", ""), args.get("max_results", 5))
            elif tool_name == "web_fetch": result = await function_web_fetch(args.get("url", ""), args.get("timeout", 30000))
            elif tool_name == "get_directions": result = await function_get_directions(args.get("origin", ""), args.get("destination", ""))
            elif tool_name == "get_weather": result = await function_get_weather(args.get("location", ""))
            elif tool_name == "generate_intelligence_dossier": result = await function_generate_intelligence_dossier(args.get("target_company"), args.get("markdown_content"))
            else: return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}
            
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": f"Tool execution error: {str(e)}"}}
    
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
    return StreamingResponse(event_generator(), media_type="text-event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

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