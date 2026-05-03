# filename: GmailMCP.py (Gmail Bridge running on Port 3035)
import os
import base64
import asyncio
import logging
import time
from typing import Any, Callable
from email.message import EmailMessage
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Google API Imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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

# Retry configuration for transient failures
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries

def get_gmail_service() -> Any:
    """Initialize and return a Gmail API service object.

    Handles OAuth2 authentication flow including:
    - Loading existing credentials from token file
    - Refreshing expired tokens
    - Initiating new OAuth2 flow if needed

    Returns:
        gmail: A Gmail API service object for making API calls.

    Raises:
        FileNotFoundError: If client_secrets.json is missing.
        RuntimeError: If OAuth2 authentication fails.
        Exception: For any other unexpected errors during initialization.
    """
    try:
        if not os.path.exists(CLIENT_SECRETS_FILE):
            logger.error(f"Client secrets file missing: {CLIENT_SECRETS_FILE}")
            raise FileNotFoundError(f"Missing {CLIENT_SECRETS_FILE}. Please ensure it exists.")

        creds = None
        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
                logger.info("Loaded Gmail credentials from token file")
            except Exception as token_err:
                logger.warning(f"Failed to load token file: {token_err}. Will re-authenticate.")
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired Gmail credentials...")
                    creds.refresh(GRequest())
                    with open(TOKEN_FILE, 'w') as token:
                        token.write(creds.to_json())
                    logger.info("Credentials refreshed successfully")
                except Exception as refresh_err:
                    logger.warning(f"Token refresh failed: {refresh_err}. Will re-authenticate.")
            
            if not creds or not creds.valid:
                try:
                    logger.info("Starting new OAuth2 authentication flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(TOKEN_FILE, 'w') as token:
                        token.write(creds.to_json())
                    logger.info("New credentials saved successfully")
                except Exception as auth_err:
                    logger.error(f"OAuth2 authentication failed: {auth_err}")
                    raise RuntimeError(f"Gmail authentication failed: {str(auth_err)}")

        service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail service initialized successfully")
        return service
        
    except FileNotFoundError:
        logger.error("Gmail setup incomplete - client secrets file not found")
        raise
    except RuntimeError:
        logger.error("Gmail authentication failed - check credentials")
        raise
    except Exception as e:
        logger.critical(f"Unexpected error initializing Gmail service: {str(e)}")
        raise

def retry_on_failure(func: Callable, *args: Any, max_retries: int = MAX_RETRIES, **kwargs: Any) -> Any:
    """Retry a function call with exponential backoff on transient failures.

    Wraps function calls and retries them if they fail with specific HTTP error codes
    (429, 500, 502, 503, 504) or transient exceptions. Uses exponential backoff
    starting at RETRY_DELAY seconds.

    Args:
        func: The callable function to execute.
        *args: Positional arguments to pass to the function.
        max_retries: Maximum number of retry attempts (default: MAX_RETRIES=3).
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The return value of the successful function call.

    Raises:
        HttpError: If the function fails with a non-retryable HTTP error code.
        Exception: If all retry attempts are exhausted.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            last_exception = e
            if e.resp.status in [429, 500, 502, 503, 504]:  # Retry on these status codes
                wait_time = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Gmail API error {e.resp.status} on attempt {attempt + 1}/{max_retries}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Non-retryable Gmail API error: {e.resp.status}")
                raise
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Transient error on attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed: {str(e)}")
                raise
    if last_exception:
        raise last_exception

# --- GMAIL TOOLS ---

async def function_check_unread(limit: int = 5) -> str:
    """Fetch and display the latest unread emails from the user's Gmail inbox.

    Retrieves up to `limit` unread messages, extracts sender, subject, and snippet
    for each. Returns a formatted string with email details.

    Args:
        limit: Maximum number of unread emails to fetch (default: 5, max: 100).
            Values outside 1-100 range are normalized to 5.

    Returns:
        A formatted string listing all unread emails with their ID, sender,
        subject, and snippet. Returns an empty inbox message if none found.
    """
    try:
        if limit < 1 or limit > 100:
            logger.warning(f"Invalid limit parameter: {limit}. Normalizing to 5.")
            limit = 5
            
        logger.info(f"Fetching {limit} unread emails...")
        
        def _fetch_unread():
            service = get_gmail_service()
            results = retry_on_failure(service.users().messages().list, userId='me', labelIds=['UNREAD'], maxResults=limit).execute()
            return results
        
        results = await asyncio.to_thread(_fetch_unread)
        
        if not results:
            logger.info("No unread emails found")
            return "📭 Your inbox is clear. No unread emails."
            
        messages = results.get('messages', [])

        if not messages:
            logger.info("Inbox clear - no message objects returned")
            return "📭 Your inbox is clear. No unread emails."

        output = "📬 **Unread Emails:**\n"
        for i, msg in enumerate(messages):
            try:
                logger.info(f"Processing email {i+1}/{len(messages)} (ID: {msg['id']})")
                
                def _get_email():
                    return retry_on_failure(
                        service.users().messages().get,
                        userId='me', 
                        id=msg['id'], 
                        format='metadata', 
                        metadataHeaders=['From', 'Subject']
                    ).execute()
                
                msg_data = await asyncio.to_thread(_get_email)
                headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
                
                sender = headers.get('From', 'Unknown Sender')
                subject = headers.get('Subject', 'No Subject')
                snippet = msg_data.get('snippet', '')
                
                output += f"\n🆔 **ID:** `{msg['id']}`\n👤 **From:** {sender}\n🏷️ **Subject:** {subject}\n📝 **Snippet:** {snippet}...\n"
                
            except Exception as msg_err:
                logger.error(f"Failed to process email {i+1}: {str(msg_err)}")
                output += f"\n⚠️ Email {i+1}: Failed to load - {str(msg_err)}\n"
            
        logger.info(f"Successfully processed {len(messages)} unread emails")
        return output
        
    except FileNotFoundError as e:
        logger.error(f"Gmail setup error: {str(e)}")
        return f"❌ Gmail not configured: {str(e)}. Please set up OAuth2 credentials."
    except RuntimeError as e:
        logger.error(f"Gmail auth error: {str(e)}")
        return f"❌ Authentication failed: {str(e)}. Please check your Gmail credentials."
    except Exception as e:
        logger.critical(f"Unexpected error checking unread emails: {str(e)}")
        return f"❌ Gmail API Error (Check Unread): {str(e)}"

async def function_read_full_email(email_id: str) -> str:
    """Read the full content of a specific email and mark it as read.

    Retrieves the complete email body (handling both plain text and multipart emails),
    extracts headers (sender, subject, date), and removes the UNREAD label.
    Returns a formatted string with all email details.

    Args:
        email_id: The Gmail message ID of the email to read. Must be a non-empty string.

    Returns:
        A formatted string containing sender, subject, date, and full body content.
        Returns an error message if the email_id is invalid or the email cannot be decoded.
    """
    try:
        if not email_id or not isinstance(email_id, str):
            logger.warning("Read email called with empty or invalid email_id")
            return "❌ Invalid request: Please provide a valid email ID."
        
        logger.info(f"Reading email ID: {email_id}")
        
        def _read_email():
            service = get_gmail_service()
            message = retry_on_failure(
                service.users().messages().get,
                userId='me', 
                id=email_id, 
                format='full'
            ).execute()
            return message
        
        message = await asyncio.to_thread(_read_email)
        
        # Extract headers with error handling
        try:
            headers = {h['name']: h['value'] for h in message['payload']['headers']}
            sender = headers.get('From', 'Unknown')
            subject = headers.get('Subject', 'No Subject')
            date = headers.get('Date', 'Unknown Date')
            logger.info(f"Email headers extracted: {sender} - {subject}")
        except Exception as header_err:
            logger.warning(f"Failed to extract email headers: {str(header_err)}")
            sender = "Unknown"
            subject = "Unknown Subject"
            date = "Unknown Date"

        # Decode the body with error handling
        def get_body(payload):
            try:
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain':
                            try:
                                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            except Exception as decode_err:
                                logger.warning(f"Failed to decode text part: {str(decode_err)}")
                                continue
                        elif 'parts' in part:
                            result = get_body(part)
                            if result and result != "Could not extract plain text body.":
                                return result
                elif payload['mimeType'] == 'text/plain':
                    try:
                        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                    except Exception as decode_err:
                        logger.warning(f"Failed to decode body: {str(decode_err)}")
            except Exception as body_err:
                logger.warning(f"Error extracting email body: {str(body_err)}")
            return "Could not extract plain text body."

        try:
            body = get_body(message['payload'])
            if not body or body == "Could not extract plain text body.":
                logger.warning("No plain text body found in email")
                body = "⚠️ Could not extract text content from this email (may contain only attachments or HTML)."
        except Exception as body_err:
            logger.error(f"Unexpected error decoding email body: {str(body_err)}")
            body = "⚠️ Error decoding email body."
        
        # Mark as read with retry logic
        try:
            def _mark_as_read():
                service = get_gmail_service()
                retry_on_failure(
                    service.users().messages().modify,
                    userId='me', 
                    id=email_id, 
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
            
            await asyncio.to_thread(_mark_as_read)
            logger.info(f"Email {email_id} marked as read")
        except Exception as mark_err:
            logger.warning(f"Failed to mark email as read: {str(mark_err)}")

        return f"📖 **Full Email Read (Marked as Read)**\n\n👤 **From:** {sender}\n🏷️ **Subject:** {subject}\n📅 **Date:** {date}\n\n**Body:**\n{body}"
        
    except FileNotFoundError as e:
        logger.error(f"Gmail setup error: {str(e)}")
        return f"❌ Gmail not configured: {str(e)}. Please set up OAuth2 credentials."
    except RuntimeError as e:
        logger.error(f"Gmail auth error: {str(e)}")
        return f"❌ Authentication failed: {str(e)}. Please check your Gmail credentials."
    except Exception as e:
        logger.critical(f"Unexpected error reading email: {str(e)}")
        return f"❌ Gmail API Error (Read Full): {str(e)}"

async def function_send_gmail(to: str, subject: str, body: str) -> str:
    """Send an email to a specified recipient with full input validation.

    Creates an email message with the provided recipient, subject, and body content,
    then sends it via the Gmail API with retry logic for transient failures.

    Args:
        to: The recipient's email address. Must be a non-empty string.
        subject: The email subject line. Must be a non-empty string.
        body: The main content of the email. Must be a non-empty string.

    Returns:
        A confirmation message with the sent message ID on success, or an error
        message if validation fails, the email cannot be created, or sending fails.
    """
    try:
        # Input validation
        if not to or not isinstance(to, str):
            logger.warning("Send email called with invalid 'to' address")
            return "❌ Invalid request: Please provide a valid recipient email address."
        
        if not subject or not isinstance(subject, str):
            logger.warning("Send email called with empty subject")
            return "❌ Invalid request: Please provide an email subject."
        
        if not body or not isinstance(body, str):
            logger.warning("Send email called with empty body")
            return "❌ Invalid request: Please provide email content."
        
        logger.info(f"Sending email to {to}: {subject}")
        
        # Create email message
        try:
            message = EmailMessage()
            message.set_content(body)
            message['To'] = to
            message['From'] = 'me'
            message['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}
        except Exception as msg_err:
            logger.error(f"Failed to create email message: {str(msg_err)}")
            return f"❌ Email creation failed: {str(msg_err)}"
        
        # Send with retry logic
        def _send_email():
            service = get_gmail_service()
            return retry_on_failure(
                service.users().messages().send,
                userId="me", 
                body=create_message
            ).execute()
        
        try:
            send_message = await asyncio.to_thread(_send_email)
            logger.info(f"Email sent successfully to {to} (ID: {send_message['id']})")
            return f"✅ **Email Sent Successfully!** (Message ID: {send_message['id']})"
        except Exception as send_err:
            logger.error(f"Failed to send email after retries: {str(send_err)}")
            return f"❌ Gmail API Error (Send Email): {str(send_err)}"
        
    except FileNotFoundError as e:
        logger.error(f"Gmail setup error: {str(e)}")
        return f"❌ Gmail not configured: {str(e)}. Please set up OAuth2 credentials."
    except RuntimeError as e:
        logger.error(f"Gmail auth error: {str(e)}")
        return f"❌ Authentication failed: {str(e)}. Please check your Gmail credentials."
    except Exception as e:
        logger.critical(f"Unexpected error sending email: {str(e)}")
        return f"❌ Gmail API Error (Send Email): {str(e)}"

async def function_bulk_delete_emails(query: str) -> str:
    """Move emails matching a Gmail search query to the Trash (not permanent delete).

    Searches for emails using standard Gmail search operators (e.g., 'from:spammer.com',
    'subject:promo'), then batch-moves them to TRASH label. Processes up to 500 messages
    per request to avoid timeouts.

    Args:
        query: Standard Gmail search query string (e.g., 'from:temu.com' or 'subject:promo').
            Must be a non-empty string.

    Returns:
        A confirmation message with the count of moved emails, or a message indicating
        no matching emails were found. Returns an error message if the query is invalid.
    """
    try:
        # Input validation
        if not query or not isinstance(query, str):
            logger.warning("Bulk delete called with empty or invalid query")
            return "❌ Invalid request: Please provide a valid Gmail search query."
        
        logger.info(f"Bulk deleting emails matching query: '{query}'")
        
        def _search_and_delete():
            service = get_gmail_service()
            
            # Search for messages matching the query (grabs up to 500 at a time to prevent timeout)
            results = retry_on_failure(
                service.users().messages().list,
                userId='me', 
                q=query, 
                maxResults=500
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return {"count": 0, "error": None}
            
            message_ids = [msg['id'] for msg in messages]
            
            # Safely move them to TRASH instead of permanently deleting them
            retry_on_failure(
                service.users().messages().batchModify,
                userId='me', 
                body={'ids': message_ids, 'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
            ).execute()
            
            return {"count": len(message_ids), "error": None}
        
        result = await asyncio.to_thread(_search_and_delete)
        
        if result["count"] == 0:
            logger.info(f"No emails found matching query: '{query}'")
            return f"📭 No emails found matching the query: '{query}'"
        
        logger.info(f"Successfully moved {result['count']} emails to Trash")
        return f"✅ Successfully moved {result['count']} emails matching '{query}' to the Trash."
        
    except FileNotFoundError as e:
        logger.error(f"Gmail setup error: {str(e)}")
        return f"❌ Gmail not configured: {str(e)}. Please set up OAuth2 credentials."
    except RuntimeError as e:
        logger.error(f"Gmail auth error: {str(e)}")
        return f"❌ Authentication failed: {str(e)}. Please check your Gmail credentials."
    except Exception as e:
        logger.critical(f"Unexpected error during bulk delete: {str(e)}")
        return f"❌ Gmail API Error (Bulk Delete): {str(e)}"

# --- MCP RPC LOGIC ---
async def handle_rpc(message: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP JSON-RPC 2.0 messages for Gmail tool calls.

    Dispatches incoming RPC requests to the appropriate handler based on method name.
    Supports initialize, tools/list, tools/call, and ping methods.

    Args:
        message: A dictionary containing the JSON-RPC request with keys 'id', 'method',
            and optionally 'params'.

    Returns:
        A JSON-RPC response dictionary containing 'jsonrpc' version, 'id', and either
        a 'result' or 'error' field.
    """
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
async def get_sse(request: Request) -> StreamingResponse:
    """SSE endpoint that provides the messages URL to MCP clients.

    Sends an initial event with the /messages endpoint URL, then maintains
    a heartbeat connection every 15 seconds.

    Returns:
        A StreamingResponse with SSE format content.
    """
    async def event_generator():
        base = str(request.base_url).rstrip('/')
        yield f"event: endpoint\ndata: {base}/messages\n\n"
        while True:
            await asyncio.sleep(15)
            yield ": heartbeat\n\n"
    return StreamingResponse(event_generator(), media_type="text-event-stream")

@app.post("/messages")
@app.post("/sse")
async def post_messages(request: Request) -> JSONResponse:
    """POST endpoint for MCP JSON-RPC 2.0 messages and SSE connections.

    Processes incoming JSON-RPC requests by passing them to handle_rpc().
    Also accepts non-request POST bodies and returns a status OK response.

    Args:
        request: The FastAPI Request object containing the JSON body.

    Returns:
        A JSONResponse with either the RPC result, status ok, or an error message.
    """
    try:
        body = await request.json()
        if "id" in body: return JSONResponse(content=await handle_rpc(body))
        return JSONResponse(content={"status": "ok"})
    except Exception as e: return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)