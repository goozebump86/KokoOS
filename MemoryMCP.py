# filename: MemoryMCP.py (Infinite Recall Bridge running on Port 3021)
import os
import json
import uuid
import asyncio
import logging
from datetime import datetime
import chromadb
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Koko Infinite Recall MCP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SERVER_PORT = 3021
MCP_VERSION = "2024-11-05"

# --- DATABASE INITIALIZATION ---
# This creates a folder called 'koko_memory_db' in your current directory to permanently store the vectors
DB_PATH = os.path.join(os.getcwd(), "koko_memory_db")
chroma_client = chromadb.PersistentClient(path=DB_PATH)

# Get or create the core memory collection
try:
    memory_collection = chroma_client.get_or_create_collection(
        name="koko_core_memories",
        metadata={"hnsw:space": "cosine"} # Optimizes for semantic similarity
    )
    logger.info(f"✅ ChromaDB initialized successfully at {DB_PATH}")
except Exception as e:
    logger.error(f"❌ Failed to initialize ChromaDB: {e}")

# --- MEMORY TOOLS ---

def function_store_memory(concept: str, details: str) -> str:
    """Etches a new memory permanently into the vector database."""
    try:
        memory_id = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        timestamp = datetime.now().isoformat()
        
        # We store the details as the main document, and the concept as searchable metadata
        memory_collection.add(
            documents=[details],
            metadatas=[{"concept": concept, "timestamp": timestamp}],
            ids=[memory_id]
        )
        return f"✅ Memory successfully etched into the neural net.\nConcept: '{concept}'\nID: {memory_id}"
    except Exception as e:
        return f"❌ Failed to store memory: {str(e)}"

def function_semantic_search(query: str, n_results: int = 3) -> str:
    """Searches the database mathematically for the closest matching memories."""
    try:
        # Failsafe if the database is empty
        if memory_collection.count() == 0:
            return "The memory bank is currently empty. There is nothing to recall."
            
        results = memory_collection.query(
            query_texts=[query],
            n_results=min(n_results, memory_collection.count())
        )
        
        if not results['documents'] or not results['documents'][0]:
            return f"No highly relevant memories found for: '{query}'"
            
        formatted_results = ["🧠 **Recalled Memories:**\n"]
        for i in range(len(results['documents'][0])):
            concept = results['metadatas'][0][i].get('concept', 'Unknown')
            date = results['metadatas'][0][i].get('timestamp', '')[:10]
            document = results['documents'][0][i]
            formatted_results.append(f"🔹 **[{date}] {concept}:** {document}")
            
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"❌ Neural search failed: {str(e)}"

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
                "serverInfo": {"name": "koko-memory-mcp", "version": "1.0.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "store_memory",
                        "description": "Permanently saves a concept, rule, script, or preference into your long-term vector database.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "concept": {"type": "string", "description": "A short, descriptive title for this memory (e.g., 'YouTube FFmpeg Zoom Command')."},
                                "details": {"type": "string", "description": "The exact code, logic, or text to be remembered forever."}
                            }, "required": ["concept", "details"]
                        }
                    },
                    {
                        "name": "semantic_search",
                        "description": "Searches your long-term memory bank for information related to the query. Use this whenever you are asked to recall past projects, rules, or user preferences.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The question or topic you want to search for."},
                                "n_results": {"type": "integer", "description": "Number of memories to retrieve (default: 3).", "default": 3}
                            }, "required": ["query"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "store_memory":
            result = function_store_memory(args.get("concept"), args.get("details"))
        elif tool_name == "semantic_search":
            result = function_semantic_search(args.get("query"), args.get("n_results", 3))
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
def read_root(): return HTMLResponse(f"<h3>Koko Memory Engine Running on Port {SERVER_PORT}</h3>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)