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
    # Validate inputs first
    if not origin or not isinstance(origin, str):
        logger.warning("Get directions requested without valid origin")
        return "❌ Route calculation failed: Please provide a valid starting location."
    if not destination or not isinstance(destination, str):
        logger.warning("Get directions requested without valid destination")
        return "❌ Route calculation failed: Please provide a valid destination."
    
    logger.info(f"Calculating route from '{origin}' to '{destination}'")
    
    # Attempt geocoding with retry for transient failures
    def geocode(place, attempt=1):
        try:
            safe_place = urllib.parse.quote(place)
            url = f"https://nominatim.openstreetmap.org/search?q={safe_place}&format=json&limit=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'JuneAI-Local-Assistant'})
            with urllib.request.urlopen(req, timeout=15000) as response:
                data = json.loads(response.read().decode())
                if not data: 
                    logger.warning(f"Nominatim returned no results for '{place}'")
                    return None
                coords = f"{data[0]['lon']},{data[0]['lat']}"
                logger.info(f"Geocoded '{place}' -> {coords}")
                return coords
        except urllib.error.URLError as e:
            if attempt < 2:
                logger.warning(f"Nominatim timeout for '{place}' (attempt {attempt}), retrying...")
                import time; time.sleep(1)
                return geocode(place, attempt + 1)
            raise
        except Exception as e:
            logger.error(f"Nominatim error for '{place}': {str(e)}")
            raise

    def get_route(osrm_url, attempt=1):
        try:
            with urllib.request.urlopen(osrm_url, timeout=15000) as response:
                return json.loads(response.read().decode())
        except urllib.error.URLError as e:
            if attempt < 2:
                logger.warning(f"OSRM timeout (attempt {attempt}), retrying...")
                import time; time.sleep(1.5)
                return get_route(osrm_url, attempt + 1)
            raise

    # Geocode origin and destination with error wrapping
    try:
        coords_orig = await asyncio.to_thread(geocode, origin)
    except Exception as e:
        logger.error(f"Geocoding failed for origin '{origin}': {str(e)}")
        return f"❌ Could not resolve starting location '{origin}'. The service may be temporarily unavailable."

    try:
        coords_dest = await asyncio.to_thread(geocode, destination)
    except Exception as e:
        logger.error(f"Geocoding failed for destination '{destination}': {str(e)}")
        return f"❌ Could not resolve destination '{destination}'. The service may be temporarily unavailable."

    if not coords_orig or not coords_dest:
        missing = []
        if not coords_orig: missing.append(origin)
        if not coords_dest: missing.append(destination)
        return f"❌ Could not find GPS coordinates for: {', '.join(missing)}. Try using more specific addresses."

    # Calculate route with OSRM
    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{coords_orig};{coords_dest}?overview=false"
    try:
        route_data = await asyncio.to_thread(get_route, osrm_url)
        if not route_data or route_data.get('code') != 'Ok':
            error_msg = route_data.get('message', 'Unknown OSRM error') if route_data else 'No response from routing engine'
            logger.error(f"OSRM route calculation failed: {error_msg}")
            return f"❌ Route calculation failed: Could not compute route ({error_msg})."

        distance_miles = round((route_data['routes'][0]['distance'] / 1609.34), 1)
        duration_minutes = round(route_data['routes'][0]['duration'] / 60)
        
        logger.info(f"Route calculated: {distance_miles} miles, ~{duration_minutes} min")

        google_maps_link = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin)}&destination={urllib.parse.quote(destination)}&travelmode=driving"
        apple_maps_link = f"https://maps.apple.com/dir/{urllib.parse.quote(origin)},{urllib.parse.quote(destination)}"

        return f"=== ROUTE CALCULATED ===\n**From:** {origin}\n**To:** {destination}\n**Distance:** {distance_miles} miles\n**Estimated Drive Time:** {duration_minutes} minutes\n[Open Route in Google Maps]({google_maps_link})\n[Apple Maps]({apple_maps_link})"
    except Exception as e:
        error_type = type(e).__name__
        logger.critical(f"OSRM routing engine error for route '{origin}' -> '{destination}': {error_type} - {str(e)}")
        return f"❌ Route calculation failed ({error_type}): The routing service is unavailable. Please try again."

async def function_get_weather(location: str) -> str:
    # Validate input
    if not location or not isinstance(location, str):
        logger.warning("Weather requested without valid location")
        return "❌ Weather data unavailable: Please provide a valid city name, zip code, or coordinates."
    
    if len(location.strip()) < 2:
        logger.warning(f"Invalid weather location: '{location}'")
        return "❌ Weather data unavailable: Location must be at least 2 characters."
    
    logger.info(f"Fetching weather for: {location}")
    safe_loc = urllib.parse.quote(location)
    
    # Step 1: Geocode the location via Nominatim with error handling
    geo_url = f"https://nominatim.openstreetmap.org/search?q={safe_loc}&format=json&limit=1"
    try:
        req = urllib.request.Request(geo_url, headers={'User-Agent': 'LocAilly-Assistant'})
        with urllib.request.urlopen(req, timeout=15000) as response:
            geo_data = json.loads(response.read().decode())
        
        if not geo_data or len(geo_data) == 0:
            logger.warning(f"Nominatim found no results for location: {location}")
            return f"❌ Could not find location: '{location}'. Try a more specific address, city name, or zip code."
        
        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']
        display_name = geo_data[0]['display_name'].split(',')[0]
        logger.info(f"Geocoded '{location}' -> {display_name} ({lat}, {lon})")

    except urllib.error.URLError as e:
        error_code = e.code if hasattr(e, 'code') else 'unknown'
        logger.error(f"Nominatim geocoding failed for '{location}' (status {error_code}): {str(e)}")
        return f"❌ Location service unavailable ({error_code}). The geocoding server may be down. Try again later."
    except Exception as e:
        error_type = type(e).__name__
        logger.critical(f"Unexpected geocoding error for '{location}': {error_type} - {str(e)}")
        return f"❌ Location lookup failed ({error_type}): Unable to find coordinates for '{location}'."
    
    # Step 2: Fetch weather data from Open-Meteo with error handling
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=auto"
    
    try:
        with urllib.request.urlopen(weather_url, timeout=15000) as response:
            w_data = json.loads(response.read().decode())

    except urllib.error.URLError as e:
        error_code = e.code if hasattr(e, 'code') else 'unknown'
        logger.error(f"Open-Meteo API failed for ({lat}, {lon}) (status {error_code}): {str(e)}")
        return f"❌ Weather data unavailable. The Open-Meteo service is temporarily unreachable (error {error_code}). Try again in a few minutes."
    except Exception as e:
        error_type = type(e).__name__
        logger.critical(f"Unexpected weather API error for ({lat}, {lon}): {error_type} - {str(e)}")
        return f"❌ Weather service failure ({error_type}): Unable to retrieve forecast data."
    
    # Step 3: Validate and format the response
    try:
        if 'daily' not in w_data:
            logger.error(f"Open-Meteo returned unexpected format for {display_name}")
            return f"❌ Weather data corrupted. The API returned an unexpected format. Please try again."
        
        daily = w_data['daily']
        forecast = []
        for i in range(7):
            if i < len(daily.get('time', [])):
                entry = {
                    "date": daily['time'][i],
                    "max": round(float(daily['temperature_2m_max'][i])) if daily['temperature_2m_max'] and i < len(daily['temperature_2m_max']) else None,
                    "min": round(float(daily['temperature_2m_min'][i])) if daily['temperature_2m_min'] and i < len(daily['temperature_2m_min']) else None,
                    "code": int(daily['weather_code'][i]) if daily['weather_code'] and i < len(daily['weather_code']) else None
                }
                forecast.append(entry)
        
        result = {"location": display_name, "forecast": forecast}
        logger.info(f"Successfully retrieved 7-day weather for {display_name}")
        return f"=== WEATHER DATA RETRIEVED ===\nYou MUST pass this exact JSON block to the user wrapped in <weather_payload> tags so the UI can draw the widget:\n<weather_payload>\n{json.dumps(result)}\n</weather_payload>\nDo not write the weather out in text, just output the payload."
    
    except Exception as e:
        error_type = type(e).__name__
        logger.critical(f"Error formatting weather data for {display_name}: {error_type} - {str(e)}")
        return f"❌ Weather formatting error ({error_type}): Data was retrieved but could not be processed correctly."

async def function_web_fetch(url: str, timeout: int = 30000) -> str:
    # Validate URL format before attempting fetch
    if not url or not isinstance(url, str):
        logger.warning("Web fetch requested with empty or invalid URL")
        return "❌ Web fetch failed: No URL provided. Please provide a valid URL."
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    logger.info(f"Fetching URL: {url} (timeout: {timeout}ms)")
    
    if timeout <= 0 or timeout > 120000:
        logger.warning(f"Invalid timeout value: {timeout}. Normalizing to default.")
        timeout = 30000
    
    page = await playwright_context.new_page()
    try:
        # Navigate with comprehensive error handling for Playwright-specific errors
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception as nav_error:
            error_type = type(nav_error).__name__
            logger.error(f"Navigation error ({error_type}) for {url}: {str(nav_error)}")
            
            if "Timeout" in error_type or "timed out" in str(nav_error).lower():
                return f"❌ Web fetch timeout: The page at '{url}' did not load within {timeout}ms. The site may be slow or unreachable."
            elif "net::" in str(nav_error) or "network" in str(nav_error).lower():
                return f"❌ Network error: Unable to reach '{url}'. Check if the URL is correct and the site is accessible."
            else:
                return f"❌ Navigation failed ({error_type}): {str(nav_error)}"
        
        await page.wait_for_timeout(1500)
        logger.info(f"Page loaded successfully for {url}")
        
        # Extract title with error handling
        try:
            title = await page.title()
        except Exception as title_err:
            logger.warning(f"Could not extract page title: {str(title_err)}")
            title = "Unknown Title"
        
        # Clean and extract content with DOM manipulation
        try:
            content = await page.evaluate("""
                () => {
                    const clone = document.cloneNode(true);
                    clone.querySelectorAll('script, style, nav, footer, header, aside, .sidebar, .comments').forEach(el => el.remove());
                    return clone.body ? clone.body.innerText : '';
                }
            """)
        except Exception as eval_err:
            logger.warning(f"DOM evaluation failed for {url}: {str(eval_err)}")
            # Fallback to simple text extraction
            content = await page.evaluate("document.body.innerText || ''")
        
        if not content or len(content.strip()) == 0:
            logger.warning(f"Fetched page returned no content: {url}")
            return f"⚠️ Web fetch completed but '{url}' returned no extractable content."
        
        clean_text = " ".join(content.split())
        truncated = clean_text[:12000]
        full_length = len(clean_text)
        
        result = f"=== SCRAPED PAGE DATA: {title} ===\n\n{truncated}"
        if full_length > 12000:
            result += f"\n\n...[content truncated to 12000 chars of {full_length} total]..."
        
        logger.info(f"Successfully scraped {full_length} chars from {url}")
        return result
        
    except Exception as e:
        error_type = type(e).__name__
        logger.critical(f"Unhandled error in web_fetch for {url}: {error_type} - {str(e)}")
        return f"❌ Web fetch critical failure ({error_type}): {str(e)}. The site may be blocking automated access."
    finally:
        try:
            await page.close()
        except Exception as close_err:
            logger.warning(f"Error closing page: {str(close_err)}")

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