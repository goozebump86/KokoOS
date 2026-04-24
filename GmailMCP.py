# filename: GmailMCP.py (Gmail Bridge running on Port 3035)
import os
import base64
import asyncio
import logging
from email.message import EmailMessage
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Google API Imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GRequest
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Koko Gmail MCP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- CONFIGURATION ---
SERVER_PORT = 3035
MCP_VERSION = "2024-11-05"
BASE_KOKO_DIR = r"C:\Users\gooze\Downloads"

# Gmail API Configuration
SCOPES = ["https://mail.google.com/"]  # Full access to read, send, and modify emails
CLIENT_SECRETS_FILE = os.path.join(BASE_KOKO_DIR, "client_secrets.json")
TOKEN_FILE = os.path.join(BASE_KOKO_DIR, "gmail_token.json")

def get_gmail_service():
    """Handles OAuth2 and returns the Gmail service object."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(f"Missing {CLIENT_SECRETS_FILE}. Please ensure it exists.")

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

# --- GMAIL TOOLS ---

async def function_check_unread(limit: int = 5) -> str:
    """Fetches the latest unread emails."""
    try:
        service = await asyncio.to_thread(get_gmail_service)
        results = service.users().messages().list(userId='me', labelIds=['UNREAD'], maxResults=limit).execute()
        messages = results.get('messages', [])

        if not messages:
            return "📭 Your inbox is clear. No unread emails."

        output = "📬 **Unread Emails:**\n"
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['From', 'Subject']).execute()
            headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
            
            sender = headers.get('From', 'Unknown Sender')
            subject = headers.get('Subject', 'No Subject')
            snippet = msg_data.get('snippet', '')
            
            output += f"\n🆔 **ID:** `{msg['id']}`\n👤 **From:** {sender}\n🏷️ **Subject:** {subject}\n📝 **Snippet:** {snippet}...\n"
            
        return output
    except Exception as e:
        return f"❌ Gmail API Error (Check Unread): {str(e)}"

async def function_read_full_email(email_id: str) -> str:
    """Reads the full body of a specific email using its ID."""
    try:
        service = await asyncio.to_thread(get_gmail_service)
        message = service.users().messages().get(userId='me', id=email_id, format='full').execute()
        
        # Extract headers
        headers = {h['name']: h['value'] for h in message['payload']['headers']}
        sender = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No Subject')
        date = headers.get('Date', 'Unknown Date')

        # Decode the body
        def get_body(payload):
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    elif 'parts' in part:
                        return get_body(part)
            elif payload['mimeType'] == 'text/plain':
                return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            return "Could not extract plain text body."

        body = get_body(message['payload'])
        
        # Mark as read
        service.users().messages().modify(userId='me', id=email_id, body={'removeLabelIds': ['UNREAD']}).execute()

        return f"📖 **Full Email Read (Marked as Read)**\n\n👤 **From:** {sender}\n🏷️ **Subject:** {subject}\n📅 **Date:** {date}\n\n**Body:**\n{body}"
    except Exception as e:
        return f"❌ Gmail API Error (Read Full): {str(e)}"

async def function_send_gmail(to: str, subject: str, body: str) -> str:
    """Sends a new email."""
    try:
        service = await asyncio.to_thread(get_gmail_service)
        
        message = EmailMessage()
        message.set_content(body)
        message['To'] = to
        message['From'] = 'me'
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}
        
        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        return f"✅ **Email Sent Successfully!** (Message ID: {send_message['id']})"
    except Exception as e:
        return f"❌ Gmail API Error (Send Email): {str(e)}"

async def function_bulk_delete_emails(query: str) -> str:
    """Moves emails matching a specific Gmail search query to the Trash."""
    try:
        service = await asyncio.to_thread(get_gmail_service)
        
        # Search for messages matching the query (grabs up to 500 at a time to prevent timeout)
        results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"📭 No emails found matching the query: '{query}'"

        message_ids = [msg['id'] for msg in messages]

        # Safely move them to TRASH instead of permanently deleting them
        service.users().messages().batchModify(
            userId='me', 
            body={'ids': message_ids, 'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
        ).execute()

        return f"✅ Successfully moved {len(message_ids)} emails matching '{query}' to the Trash."
    except Exception as e:
        return f"❌ Gmail API Error (Bulk Delete): {str(e)}"

# --- MCP RPC LOGIC ---
async def handle_rpc(message: dict) -> dict:
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": "koko-gmail-mcp", "version": "1.1.0"}}
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "check_unread_emails",
                        "description": "Checks the user's Gmail inbox for unread emails and returns the sender, subject, and ID.",
                        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}}
                    },
                    {
                        "name": "read_full_email",
                        "description": "Reads the entire body of an email and automatically marks it as read. Requires the email ID.",
                        "inputSchema": {
                            "type": "object", 
                            "properties": {"email_id": {"type": "string", "description": "The ID of the email to read."}}, 
                            "required": ["email_id"]
                        }
                    },
                    {
                        "name": "send_gmail",
                        "description": "Sends an email from the user's Gmail account.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "to": {"type": "string"},
                                "subject": {"type": "string"},
                                "body": {"type": "string"}
                            }, "required": ["to", "subject", "body"]
                        }
                    },
                    {
                        "name": "bulk_delete_emails",
                        "description": "Bulk deletes (moves to trash) emails from Gmail matching a specific search query. Koko: Use standard Gmail search operators like 'from:temu.com' or 'subject:Temu'.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The standard Gmail search query (e.g. 'from:spammer@email.com' or 'subject:promo')."}
                            }, "required": ["query"]
                        }
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "check_unread_emails": result = await function_check_unread(args.get("limit", 5))
        elif tool_name == "read_full_email": result = await function_read_full_email(args.get("email_id"))
        elif tool_name == "send_gmail": result = await function_send_gmail(args.get("to"), args.get("subject"), args.get("body"))
        elif tool_name == "bulk_delete_emails": result = await function_bulk_delete_emails(args.get("query"))
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