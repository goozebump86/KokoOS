# filename: JellyfinMCP.py (Jellyfin Media Server Bridge running on Port 3010)
import asyncio
import json
from typing import Any, Optional
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Koko Jellyfin MCP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# === SERVER CONFIGURATIONS ===
JELLYFIN_URL = "http://192.168.1.83:8899"
JELLYFIN_API_KEY = "76fae420bef24643bfc4130f9b3a1bec"
SERVER_PORT = 3010

# --- JELLYFIN TOOLS ---

async def function_get_library_stats() -> str:
    """Gets the total count of movies, TV shows, episodes, and songs on the Jellyfin server.

    Returns:
        str: Formatted string with library statistics including movie, series, episode, song, and album counts.
    """
    url = f"{JELLYFIN_URL}/Items/Counts"
    params = {'api_key': JELLYFIN_API_KEY}
    
    try:
        response = await asyncio.to_thread(requests.get, url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        stats = (
            f"📊 **Jellyfin Library Stats:**\n"
            f"🎬 Movies: {data.get('MovieCount', 0)}\n"
            f"📺 TV Shows: {data.get('SeriesCount', 0)}\n"
            f"🎞️ Episodes: {data.get('EpisodeCount', 0)}\n"
            f"🎵 Songs: {data.get('SongCount', 0)}\n"
            f"💿 Albums: {data.get('AlbumCount', 0)}"
        )
        return stats
    except Exception as e:
        return f"❌ Jellyfin API Error (Stats): {str(e)}"

async def function_get_latest_media(item_type: Optional[str] = "Movie,Series", limit: Optional[int] = 5) -> str:
    """Pulls a list of the most recently added media to the Jellyfin server.

    Args:
        item_type (str, optional): Type of media to check. Accepts 'Movie', 'Series', or 'Movie,Series'. Defaults to 'Movie,Series'.
        limit (int, optional): Number of recent items to return. Defaults to 5.

    Returns:
        str: Formatted string listing the most recently added media items with name, year, type, and genres.
    """
    url = f"{JELLYFIN_URL}/Items"
    params = {
        'api_key': JELLYFIN_API_KEY,
        'IncludeItemTypes': item_type,
        'Recursive': 'true',
        'SortBy': 'DateCreated',
        'SortOrder': 'Descending',
        'Fields': 'Overview,Genres,ProductionYear',
        'Limit': limit
    }
    
    try:
        response = await asyncio.to_thread(requests.get, url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        items = data.get("Items", [])
        
        if not items:
            return f"❌ No recent {item_type} found in the library."
            
        res_str = f"🌟 **Latest Additions ({item_type}):**\n"
        for i, item in enumerate(items):
            year = item.get("ProductionYear", "Unknown")
            genres = ", ".join(item.get("Genres", [])[:3])
            res_str += f"{i+1}. **{item.get('Name')}** ({year}) - {item.get('Type')} | Genres: {genres}\n"
            
        return res_str
    except Exception as e:
        return f"❌ Jellyfin API Error (Latest): {str(e)}"

async def function_search_media(query: Optional[str], limit: Optional[int] = 5) -> str:
    """Searches the user's local Jellyfin media server for movies, shows, audio, or genres. Returns download links.

    Args:
        query (str): The name, genre, or keyword to search for.
        limit (int, optional): Max results to return. Defaults to 5.

    Returns:
        str: Formatted string with search results including item names, years, types, overviews, poster URLs, and download links.
    """
    url = f"{JELLYFIN_URL}/Items"
    params = {
        'api_key': JELLYFIN_API_KEY,
        'IncludeItemTypes': 'Movie,Series,Audio',
        'Recursive': 'true',
        'SearchTerm': query,
        'Fields': 'Overview,Genres,ProductionYear',
        'Limit': limit
    }
    
    try:
        response = await asyncio.to_thread(requests.get, url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        items = data.get("Items", [])
        
        if not items:
            return f"❌ No media found in the library matching '{query}'."

        res_str = f"🔍 **Search Results for '{query}':**\n"
        for i, item in enumerate(items):
            year = item.get("ProductionYear", "Unknown")
            genres = ", ".join(item.get("Genres", []))
            overview = item.get("Overview", "No overview available.")
            item_id = item.get("Id")
            
            # Truncate overview if it's too long
            if len(overview) > 150:
                overview = overview[:147] + "..."
                
            res_str += f"\n{i+1}. **{item.get('Name')}** ({year}) [{item.get('Type')}]\n"
            res_str += f"   📝 {overview}\n"
            # THESE ARE THE CRITICAL LINKS KOKO NEEDS TO SEE:
            res_str += f"   🖼️ Poster: {JELLYFIN_URL}/Items/{item_id}/Images/Primary\n"
            res_str += f"   ⬇️ Download/Stream: {JELLYFIN_URL}/Items/{item_id}/Download?api_key={JELLYFIN_API_KEY}\n"

        return res_str
    except Exception as e:
        return f"❌ Jellyfin API Error (Search): {str(e)}"

# --- MCP RPC LOGIC ---
@app.post("/messages")
async def handle_rpc(request: Request) -> JSONResponse:
    """Handles incoming RPC requests for the Jellyfin MCP server.

    Routes 'initialize', 'tools/list', and 'tools/call' methods to their respective handlers.
    Returns JSON-RPC 2.0 compliant responses.

    Args:
        request (Request): FastAPI request object containing the JSON-RPC payload.

    Returns:
        JSONResponse: JSON-RPC 2.0 response with result or error details.
    """
    body = await request.json()
    method = body.get("method")
    
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0", "id": body.get("id"), "result": {
                "protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "koko-jellyfin-mcp", "version": "2.1"}
            }
        })
        
    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0", "id": body.get("id"), "result": {
                "tools": [
                    {
                        "name": "get_library_stats",
                        "description": "Gets the total count of movies, TV shows, episodes, and songs on the Jellyfin server.",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "get_latest_media",
                        "description": "Pulls a list of the most recently added media to the server.",
                        "inputSchema": {
                            "type": "object", 
                            "properties": {
                                "item_type": {"type": "string", "description": "Type of media to check (e.g., 'Movie', 'Series', or 'Movie,Series')", "default": "Movie,Series"},
                                "limit": {"type": "integer", "description": "Number of recent items to return (default 5)", "default": 5}
                            }
                        }
                    },
                    {
                        "name": "search_media_library",
                        "description": "Searches the user's local Jellyfin media server for a movie, show, or song. Returns links to download the files.",
                        "inputSchema": {
                            "type": "object", 
                            "properties": {
                                "query": {"type": "string", "description": "The name, genre, or keyword to search for."},
                                "limit": {"type": "integer", "description": "Max results to return.", "default": 5}
                            }, 
                            "required": ["query"]
                        }
                    }
                ]
            }
        })
        
    elif method == "tools/call":
        args = body.get("params", {}).get("arguments", {})
        tool_name = body["params"]["name"]
        
        try:
            if tool_name == "get_library_stats":
                res = await function_get_library_stats()
            elif tool_name == "get_latest_media":
                res = await function_get_latest_media(args.get("item_type", "Movie,Series"), args.get("limit", 5))
            elif tool_name == "search_media_library":
                res = await function_search_media(args.get("query", ""), args.get("limit", 5))
            else:
                return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": "Tool not found"}})
                
            return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"), "result": {"content": [{"type": "text", "text": res}]}})
        except Exception as e:
            return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32000, "message": f"Execution error: {str(e)}"}})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)