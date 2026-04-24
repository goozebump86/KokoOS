# outlookmcp.py
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright, BrowserContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_PORT = 3015
MCP_VERSION = "2024-11-05"

playwright_engine = None
playwright_context: BrowserContext = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global playwright_engine, playwright_context
    logger.info("🚀 Booting persistent Playwright engine...")
    user_data_dir = os.path.join(os.getcwd(), "outlook_session_data")
    
    try:
        playwright_engine = await async_playwright().start()
        playwright_context = await playwright_engine.chromium.launch_persistent_context(
            user_data_dir, 
            headless=False, 
            args=['--disable-blink-features=AutomationControlled']
        )
        logger.info("✅ Persistent browser ready!")
    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
        
    yield 
    
    if playwright_context:
        await playwright_context.close()
    if playwright_engine:
        await playwright_engine.stop()

app = FastAPI(title="Loc.Ai.lly Stateful Outlook MCP", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

async def clean_slate(page):
    """Presses Escape to clear any leftover menus, popups, or selections."""
    await page.keyboard.press("Escape")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)

async def get_latest_emails_playwright(limit=5):
    page = await playwright_context.new_page()
    try:
        await page.goto("https://outlook.live.com/mail/0/inbox", wait_until="domcontentloaded")
        await page.wait_for_selector('div[aria-label="Message list"]', timeout=15000)
        await page.wait_for_timeout(2000)
        await clean_slate(page)

        message_list = page.locator('div[aria-label="Message list"]')
        results = []
        
        attempts = 0
        while len(results) < limit and attempts < 15:
            rows = await message_list.locator('[draggable="true"]').all()
            if not rows: break
                
            for row in rows:
                if len(results) >= limit: break
                try:
                    text = await row.inner_text()
                    lines = [t.strip() for t in text.split('\n') if t.strip()]
                    
                    if len(lines) >= 3 and "Focused" not in lines[0] and "Other" not in lines[0]:
                        if len(results) == 0 or text not in [r.get('_raw_text', '') for r in results]:
                            results.append({
                                "from": lines[0],
                                "subject": lines[1],
                                "preview": " ".join(lines[2:])[:200] + "...",
                                "_raw_text": text 
                            })
                except: continue
            
            if len(results) < limit and rows:
                try:
                    await rows[-1].scroll_into_view_if_needed()
                    await page.wait_for_timeout(1000) 
                except: pass
            attempts += 1
            
        for r in results:
            r.pop('_raw_text', None)
            
        return results
    finally:
        await page.close()

async def delete_email_playwright(subject: str):
    page = await playwright_context.new_page()
    try:
        await page.goto("https://outlook.live.com/mail/0/inbox", wait_until="domcontentloaded")
        await page.wait_for_selector('div[aria-label="Message list"]', timeout=15000)
        await page.wait_for_timeout(2000)
        await clean_slate(page)

        message_list = page.locator('div[aria-label="Message list"]')
        attempts = 0
        
        while attempts < 15:
            rows = await message_list.locator('[draggable="true"]').all()
            for row in rows:
                try:
                    text = await row.inner_text()
                    if subject.lower() in text.lower():
                        await row.scroll_into_view_if_needed()
                        await row.hover()
                        await page.wait_for_timeout(300)
                        await row.click() 
                        await page.wait_for_timeout(1000)
                        await page.keyboard.press("Delete") 
                        await page.wait_for_timeout(2000)
                        return f"✅ Successfully deleted email: '{subject}'"
                except: continue
                
            if rows:
                try:
                    await rows[-1].scroll_into_view_if_needed()
                    await page.wait_for_timeout(1000)
                except: pass
            attempts += 1
            
        return f"❌ Could not find an email with the subject: '{subject}'"
    finally:
        await page.close()

async def move_email_playwright(subject: str, folder: str):
    page = await playwright_context.new_page()
    try:
        await page.goto("https://outlook.live.com/mail/0/inbox", wait_until="domcontentloaded")
        await page.wait_for_selector('div[aria-label="Message list"]', timeout=15000)
        await page.wait_for_timeout(2000)
        await clean_slate(page)

        message_list = page.locator('div[aria-label="Message list"]')
        attempts = 0
        found = False
        
        while attempts < 15:
            rows = await message_list.locator('[draggable="true"]').all()
            for row in rows:
                try:
                    text = await row.inner_text()
                    if subject.lower() in text.lower():
                        await row.scroll_into_view_if_needed()
                        await row.hover()
                        await page.wait_for_timeout(300)
                        await row.click()
                        found = True
                        break
                except: continue
            if found: break
            
            if rows:
                try:
                    await rows[-1].scroll_into_view_if_needed()
                    await page.wait_for_timeout(1000)
                except: pass
            attempts += 1
            
        if not found:
            return f"❌ Could not find an email with the subject: '{subject}'"

        await page.wait_for_timeout(1000)
        await page.evaluate("""
            () => {
                let btns = Array.from(document.querySelectorAll('button'));
                let moveBtn = btns.find(b => b.getAttribute('aria-label') && b.getAttribute('aria-label').includes('Move to'));
                if(moveBtn) moveBtn.click();
            }
        """)
        await page.wait_for_timeout(1500)
        await page.evaluate(f"""
            (folder) => {{
                let spans = Array.from(document.querySelectorAll('span'));
                let folderSpan = spans.find(s => s.innerText.trim().toLowerCase() === folder.toLowerCase());
                if(folderSpan) folderSpan.click();
            }}
        """, folder)
        await page.wait_for_timeout(2000)
        return f"✅ Successfully moved email '{subject}' to '{folder}'"
    finally:
        await page.close()

async def bulk_delete_emails_playwright(latest_n: int = 0, subjects: list = None):
    page = await playwright_context.new_page()
    try:
        await page.goto("https://outlook.live.com/mail/0/inbox", wait_until="domcontentloaded")
        await page.wait_for_selector('div[aria-label="Message list"]', timeout=15000)
        await page.wait_for_timeout(2000)
        await clean_slate(page)

        message_list = page.locator('div[aria-label="Message list"]')
        selected_count = 0

        if latest_n > 0:
            rows = await message_list.locator('[draggable="true"]').all()
            if not rows:
                return "❌ No emails found to delete."

            await rows[0].focus()
            await rows[0].click()
            await page.wait_for_timeout(500)
            selected_count = 1

            if latest_n > 1:
                await page.keyboard.down("Shift")
                for _ in range(latest_n - 1):
                    await page.keyboard.press("ArrowDown")
                    await page.wait_for_timeout(200) 
                    selected_count += 1
                await page.keyboard.up("Shift")
            
            await page.wait_for_timeout(500)

        elif subjects:
            attempts = 0
            seen_texts = set()
            
            await page.keyboard.down("Control")
            
            while attempts < 20:
                rows = await message_list.locator('[draggable="true"]').all()
                if not rows: break
                
                for row in rows:
                    try:
                        text = await row.inner_text()
                        if not text or text in seen_texts: continue
                        
                        if any(sub.lower() in text.lower() for sub in subjects):
                            seen_texts.add(text) 
                            await row.scroll_into_view_if_needed()
                            await page.wait_for_timeout(300)
                            
                            await row.click()
                            selected_count += 1
                            await page.wait_for_timeout(300)
                    except: continue
                    
                try:
                    await rows[-1].scroll_into_view_if_needed()
                    await page.wait_for_timeout(1200) 
                except: pass
                attempts += 1
                
            await page.keyboard.up("Control")

        if selected_count == 0:
            return "❌ No emails matched the criteria."

        await page.wait_for_timeout(1000)
        await page.keyboard.press("Delete")
        await page.wait_for_timeout(3000) 
        
        return f"✅ Successfully bulk-deleted {selected_count} emails!"
    except Exception as e:
        await page.keyboard.up("Shift")
        await page.keyboard.up("Control")
        return f"❌ Batch Delete failed: {str(e)}"
    finally:
        await page.close()

# --- THE NEW COMPOSE EMAIL FUNCTION ---
async def compose_email_playwright(to_email: str, subject: str, body: str):
    page = await playwright_context.new_page()
    try:
        await page.goto("https://outlook.live.com/mail/0/inbox", wait_until="domcontentloaded")
        await page.wait_for_selector('div[aria-label="Message list"]', timeout=15000)
        await page.wait_for_timeout(2000)
        await clean_slate(page)

        # 1. Click 'New mail' button
        new_mail_btn = page.locator('button:has-text("New mail")').first
        await new_mail_btn.click()
        
        # Wait for the compose pane to open
        await page.wait_for_selector('[aria-label="To"]', timeout=10000)
        await page.wait_for_timeout(1500)

        # 2. Fill the "To" field
        to_field = page.locator('[aria-label="To"]').first
        await to_field.fill(to_email)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter") # Lock in the email address chip
        await page.wait_for_timeout(500)
        
        # 3. 🚀 THE FIX: Fill the "Subject" using multi-match fallback selectors
        subject_field = page.locator('input[placeholder="Add a subject"], input[aria-label="Subject"], [aria-label="Add a subject"]').first
        await subject_field.click()
        await page.wait_for_timeout(200)
        await subject_field.fill(subject)
        await page.wait_for_timeout(500)
        
        # 4. 🚀 THE FIX: Fill the Body using a CSS wildcard (*= means "contains")
        body_field = page.locator('[aria-label*="Message body"]').first
        await body_field.click() # Focus the editor
        await page.wait_for_timeout(500)
        await page.keyboard.type(body) # Type it out like a human
        await page.wait_for_timeout(1000)
        
        # 5. Send using Universal Microsoft Shortcut
        await page.keyboard.press("Control+Enter")
        
        # Wait a few seconds for the send animation
        await page.wait_for_timeout(3500) 
        
        return f"✅ Successfully composed and sent email to {to_email} with subject '{subject}'"
    except Exception as e:
        return f"❌ Compose Email failed: {str(e)}"
    finally:
        await page.close()

async def handle_rpc(message: dict) -> dict:
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": "stateful-outlook-server", "version": "10.0"}}
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {"name": "check_inbox", "description": "Read the latest emails directly from the Outlook Web interface.", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Number of emails", "default": 5}}}},
                    {"name": "delete_email", "description": "Delete a specific email by providing its subject line.", "inputSchema": {"type": "object", "properties": {"subject": {"type": "string"}}, "required": ["subject"]}},
                    {"name": "move_email", "description": "Move an email to a folder by providing its subject.", "inputSchema": {"type": "object", "properties": {"subject": {"type": "string"}, "folder": {"type": "string"}}, "required": ["subject", "folder"]}},
                    {
                        "name": "compose_email",
                        "description": "Compose and send a new email from the user's account.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "to_email": {"type": "string", "description": "The exact email address of the recipient"},
                                "subject": {"type": "string", "description": "The subject line of the email"},
                                "body": {"type": "string", "description": "The main body content of the email to be sent"}
                            },
                            "required": ["to_email", "subject", "body"]
                        }
                    },
                    {
                        "name": "bulk_delete_emails",
                        "description": "Deletes multiple emails at once. Can blindly delete the top N latest emails, or delete a list of specific subjects.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "latest_n": {
                                    "type": "integer", 
                                    "description": "Number of top emails to blindly delete (e.g., 20). Leave as 0 if using specific subjects.", 
                                    "default": 0
                                },
                                "subjects": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "A list of exact subjects to delete. Leave empty if using latest_n."
                                }
                            }
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        try:
            if tool_name == "check_inbox":
                result = await get_latest_emails_playwright(args.get("limit", 5))
                result_text = json.dumps({"status": "success", "emails": result}, indent=2)
            elif tool_name == "delete_email":
                result_text = await delete_email_playwright(args.get("subject", ""))
            elif tool_name == "move_email":
                result_text = await move_email_playwright(args.get("subject", ""), args.get("folder", ""))
            elif tool_name == "compose_email":
                result_text = await compose_email_playwright(args.get("to_email", ""), args.get("subject", ""), args.get("body", ""))
            elif tool_name == "bulk_delete_emails":
                result_text = await bulk_delete_emails_playwright(args.get("latest_n", 0), args.get("subjects", []))
            else:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}}
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result_text}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": f"Tool error: {str(e)}"}}
    elif method == "ping": return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    else: return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

@app.post("/messages")
async def post_messages(request: Request):
    try:
        body = await request.json()
        if "id" in body:
            return JSONResponse(content=await handle_rpc(body))
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting Stateful Outlook MCP on port {SERVER_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)