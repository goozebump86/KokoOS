# filename: hermes.py
import asyncio
import json
import os
import httpx
import time
import uuid
import base64
import emoji
import hashlib
import subprocess
import sys
import logging
from datetime import datetime
from openai import AsyncOpenAI
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("KokoOS.Hermes")

try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

# Textual Imports for Koko OS
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Container, VerticalScroll
from textual.widgets import Static, Input, TextArea, Footer, Label, Button, Header, ProgressBar
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.events import Key
from textual.message import Message
from rich.text import Text
from rich.markdown import Markdown
from rich.console import Group

# --- OPENCODE ASCII HEADER ---
KOKO_HEADER = """
[white bold]██╗  ██╗ ██████╗ ██╗  ██╗ ██████╗ [/][#8b949e bold] ██████╗ ██████╗ ██████╗ ███████╗[/]
[white bold]██║ ██╔╝██╔═══██╗██║ ██╔╝██╔═══██╗[/][#8b949e bold]██╔════╝██╔═══██╗██╔══██╗██╔════╝[/]
[white bold]█████╔╝ ██║   ██║█████╔╝ ██║   ██║[/][#8b949e bold]██║     ██║   ██║██║  ██║█████╗  [/]
[white bold]██╔═██╗ ██║   ██║██╔═██╗ ██║   ██║[/][#8b949e bold]██║     ██║   ██║██║  ██║██╔══╝  [/]
[white bold]██║  ██╗╚██████╔╝██║  ██╗╚██████╔╝[/][#8b949e bold]╚██████╗╚██████╔╝██████╔╝███████╗[/]
[white bold]╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ [/][#8b949e bold] ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝[/]
"""

# --- INTERACTIVE SETTINGS MODAL ---
class SettingsModal(ModalScreen[dict]):
    CSS = """
    SettingsModal { align: center middle; background: rgba(10, 10, 10, 0.9); }
    #settings_dialog { width: 85; height: auto; background: #0a0a0a; border: solid #3fb950; padding: 1 2; }
    #settings_title { margin-bottom: 1; color: #3fb950; text-style: bold; text-align: center; }
    .form_row { layout: horizontal; height: 3; margin-bottom: 1; }
    .form_label { width: 25; content-align: left middle; color: #c9d1d9; }
    .form_input { width: 1fr; background: #0a0a0a; border: solid #30363d; color: #58a6ff; }
    .btn_row { layout: horizontal; align: center middle; height: 3; margin-top: 2; }
    Button { margin-left: 2; margin-right: 2; background: #0a0a0a; border: solid #30363d; color: #c9d1d9; }
    Button:hover { border: solid #58a6ff; color: #58a6ff; }
    #btn_save { border: solid #3fb950; color: #3fb950; }
    #btn_save:hover { background: #3fb950; color: white; }
    """
    def __init__(self, current_settings):
        super().__init__()
        self.s = current_settings

    def compose(self) -> ComposeResult:
        llm = self.s.get("llm_settings", {})
        gemini = self.s.get("gemini_settings", {})
        mem = self.s.get("memory", {})
        gw = self.s.get("gateway", {})
        tel = self.s.get("telecom", {})

        with Container(id="settings_dialog"):
            yield Static("KOKO OS CONFIGURATION [CTRL+S]", id="settings_title")
            
            with Horizontal(classes="form_row"):
                yield Label("Active Engine (local/gemini):", classes="form_label")
                yield Input(value=self.s.get("active_engine", "local"), id="set_engine", classes="form_input")
            with Horizontal(classes="form_row"):
                yield Label("Gemini API Key:", classes="form_label")
                yield Input(value=gemini.get("api_key", ""), id="set_gemini_key", classes="form_input", password=True)
            with Horizontal(classes="form_row"):
                yield Label("Local Model Name:", classes="form_label")
                yield Input(value=llm.get("model", ""), id="set_model", classes="form_input")
            with Horizontal(classes="form_row"):
                yield Label("Max Context (Tkns):", classes="form_label")
                yield Input(value=str(llm.get("max_tokens", 128000)), id="set_ctx", classes="form_input")
            with Horizontal(classes="form_row"):
                yield Label("Cron Tick (Sec):", classes="form_label")
                yield Input(value=str(gw.get("tick_rate_seconds", 60)), id="set_tick", classes="form_input")
            with Horizontal(classes="form_row"):
                yield Label("Telegram Token:", classes="form_label")
                yield Input(value=tel.get("bot_token", ""), id="set_tg_token", classes="form_input")
                
            with Horizontal(classes="btn_row"):
                yield Button("Cancel", id="btn_cancel")
                yield Button("Save", id="btn_save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_save":
            try:
                self.s["active_engine"] = self.query_one("#set_engine").value.strip().lower()
                self.s.setdefault("gemini_settings", {})["api_key"] = self.query_one("#set_gemini_key").value.strip()
                self.s.setdefault("llm_settings", {})["model"] = self.query_one("#set_model").value
                self.s["llm_settings"]["max_tokens"] = int(self.query_one("#set_ctx").value)
                self.s.setdefault("gateway", {})["tick_rate_seconds"] = int(self.query_one("#set_tick").value)
                self.s.setdefault("telecom", {})["bot_token"] = self.query_one("#set_tg_token").value
                self.dismiss(self.s)
            except ValueError:
                pass 

class QuitModal(ModalScreen[bool]):
    CSS = """
    QuitModal { align: center middle; background: rgba(10, 10, 10, 0.9); }
    #quit_dialog { width: 40; height: auto; background: #0a0a0a; border: solid #da3633; padding: 2; text-align: center; }
    #quit_title { margin-bottom: 1; color: #da3633; text-style: bold; }
    .quit_btn_row { layout: horizontal; align: center middle; height: 3; margin-top: 1; }
    Button { margin: 0 1; background: #0a0a0a; border: solid #30363d; color: #da3633; }
    Button:hover { background: #da3633; color: white; border: solid #da3633; }
    """
    def compose(self) -> ComposeResult:
        with Container(id="quit_dialog"):
            yield Static("Terminate Koko OS Shell?", id="quit_title")
            with Horizontal(classes="quit_btn_row"):
                yield Button("Cancel", id="btn_no")
                yield Button("Yes (Quit)", id="btn_yes")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_no":
            self.dismiss(False)
        elif event.button.id == "btn_yes":
            self.dismiss(True)

# --- MCP Tool Management ---
class MCPManager:
    def __init__(self, saved_servers=None):
        self.servers = saved_servers if saved_servers else []
        self.tool_directory = {}
        self.available_tools = []

    async def discover_tools(self):
        self.available_tools = []
        self.tool_directory = {}
        seen_tool_names = set() 
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            for url in self.servers:
                try:
                    res = await client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
                    data = res.json()
                    if "result" in data and "tools" in data["result"]:
                        for tool in data["result"]["tools"]:
                            name = tool["name"]
                            if name not in seen_tool_names:
                                self.available_tools.append({
                                    "type": "function", 
                                    "function": {
                                        "name": name, 
                                        "description": tool["description"], 
                                        "parameters": tool["inputSchema"]
                                    }
                                })
                                self.tool_directory[name] = url
                                seen_tool_names.add(name)
                except Exception as e:
                    logger.warning(f"MCP discovery failed for {url}: {e}")

# --- RETRY DECORATOR FOR NETWORK TOOLS ---
async def retry_on_failure(func, *args, max_retries=2, delay=1.0, **kwargs):
    """Retries a function on failure with exponential backoff."""
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (httpx.HTTPError, ConnectionError, TimeoutError) as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = delay * (2 ** attempt)
                logger.warning(f"Network error on attempt {attempt + 1}/{max_retries + 1}: {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
    raise last_exception

# --- CUSTOM CHAT TEXT AREA ---
class ChatTextArea(TextArea):
    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self.text))
        elif event.key == "shift+enter":
            event.prevent_default()
            event.stop()
            try:
                self.insert("\n")
            except AttributeError:
                try:
                    self.action_insert_new_line()
                except:
                    pass

class KokoAgentApp(App):
    TITLE = "KOKO CODE :: OS DIRECTOR SHELL"
    
    CSS = """
    Screen { background: #0a0a0a; color: #c9d1d9; }
    #header_logo { text-align: center; width: 100%; margin-top: 1; margin-bottom: 1; }
    #main_layout { layout: horizontal; width: 100%; height: 1fr; }
    #sidebar { width: 35; height: 100%; border-right: solid #30363d; padding: 1; display: none; background: #0a0a0a; }
    #sidebar.active { display: block; }
    #sidebar_title { text-style: bold; color: #3fb950; margin-bottom: 1; text-align: center; }
    #project_tree { color: #8b949e; }
    #chat_area { width: 1fr; height: 100%; }
    #chat_log { width: 100%; height: 1fr; overflow-y: auto; scrollbar-background: #0a0a0a; scrollbar-color: #30363d; padding: 0 2; }
    #input_container { height: 7; background: #0a0a0a; border-top: solid #30363d; margin-bottom: 1; padding-top: 1; }
    #koko_input { width: 100%; height: 1fr; background: #21262d; color: #58a6ff; border: none; }
    #koko_input:focus { border: none; }
    #mode_indicator { width: 100%; height: 1; content-align: left middle; color: #8b949e; text-style: bold; margin-top: 1; }
    #mode_indicator.build_mode { color: #58a6ff; }
    #mode_indicator.plan_mode { color: #3fb950; }
    
    .msg-user { color: #58a6ff; text-style: bold; margin-top: 1; }
    .msg-koko { color: #c9d1d9; margin-top: 1; }
    .msg-thought { color: #8b949e; text-style: dim; }
    .msg-remote { color: #ff9d00; margin-top: 1; }
    .msg-tool { color: #c9d1d9; text-style: italic; }
    .msg-sys { color: #8b949e; }
    .msg-error { color: #da3633; margin-top: 1; text-style: bold; }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "request_quit", "Powerdown", show=True),
        Binding("ctrl+s", "command_settings", "Settings", show=True),
        Binding("f2", "toggle_mode", "Toggle Plan/Build", show=True),
        Binding("f3", "paste_image", "Attach Image", show=True),
        Binding("f4", "toggle_engine", "Switch Engine", show=True),
        Binding("f5", "refresh_mcp", "Sync MCP", show=True),
        Binding("f8", "toggle_mic", "🎤 Mic", show=True), 
        Binding("escape", "abort", "Stop", show=True)
    ]

    def __init__(self):
        super().__init__()
        self.settings = self.load_settings()
        
        # --- ENGINE ROUTING ARCHITECTURE ---
        self.active_engine = self.settings.get("active_engine", "local")
        
        # Local Setup
        api_base = self.settings.get("llm_settings", {}).get("api_base", "http://localhost:8080/v1")
        api_key = self.settings.get("llm_settings", {}).get("api_key", "local")
        self.model_name = self.settings.get("llm_settings", {}).get("model", "qwen-35b")
        self.context_limit = self.settings.get("llm_settings", {}).get("max_tokens", 128000)
        self.local_client = AsyncOpenAI(base_url=api_base, api_key=api_key)
        
        # Gemini API Setup
        self.gemini_key = self.settings.get("gemini_settings", {}).get("api_key", "")
        self.gemini_model = self.settings.get("gemini_settings", {}).get("model", "gemini-1.5-pro")
        self.gemini_base = self.settings.get("gemini_settings", {}).get("api_base", "https://generativelanguage.googleapis.com/v1beta/openai/")
        if self.gemini_key and self.gemini_key != "YOUR_GEMINI_API_KEY":
            self.gemini_client = AsyncOpenAI(base_url=self.gemini_base, api_key=self.gemini_key)
        else:
            self.gemini_client = None

        self.mem_dir = self.settings.get("memory", {}).get("memory_dir", "memory")
        self.heartbeat_file = self.settings.get("memory", {}).get("heartbeat_file", "heartbeat.md")
        self.long_term_mem = os.path.join(self.mem_dir, "MEMORY.md")
        self.cron_db = os.path.join(self.mem_dir, "cron.json")
        self.cron_inbox = os.path.join(self.mem_dir, "cron-inbox.md")
        self.context_cache_file = os.path.join(self.mem_dir, "context_cache.json")
        
        # --- PASSIVE OBSERVER SETUP ---
        self.passive_enabled = False
        self.passive_interval = 60
        self.last_passive_time = 0
        self.last_screenshot_hash = None
        self.vision_collection = None
        
        if HAS_CHROMA:
            try:
                self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.mem_dir, "vision_db"))
                self.vision_collection = self.chroma_client.get_or_create_collection(name="passive_vision")
            except Exception:
                pass
        
        self.mcp_urls = self.settings.get("mcp_servers", [])
        self.mcp = MCPManager(self.mcp_urls)
        
        self.total_tokens = 0
        self.is_processing = False 
        self.abort_flag = False 
        self.sub_agents_enabled = self.settings.get("sub_agents", {}).get("enabled", True)
        
        self.os_mode = "BUILD"
        
        self.tg_enabled = self.settings.get("telecom", {}).get("telegram_enabled", False)
        self.tg_token = self.settings.get("telecom", {}).get("bot_token", "")
        self.tg_chats = [str(x) for x in self.settings.get("telecom", {}).get("allowed_chat_ids", [])]
        
        self.setup_openclaw_fs()
        self.tg_offset_file = os.path.join(self.mem_dir, "tg_offset.txt")
        try:
            self.tg_offset = int(open(self.tg_offset_file, "r").read().strip())
        except:
            self.tg_offset = 0
        
        self.chat_history = []
        self.initialize_agent_mind()

        # 👇 PASTE STEP 3 HERE 👇
        # --- AUDIO PIPELINE SETUP ---
        self.is_recording = False
        self.audio_frames = []
        self.audio_stream = None
        # Using tiny.en on auto device (usually CPU) so it doesn't fight Qwen for VRAM
        self.whisper_model = WhisperModel("tiny.en", device="auto", compute_type="default")
        # 👆 PASTE STEP 3 HERE 👆

        self.native_tools = [
            {"type": "function", "function": {"name": "read_local_file", "description": "Reads local files.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
            {"type": "function", "function": {"name": "write_local_file", "description": "Writes local files.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]}}},
            {"type": "function", "function": {"name": "edit_local_file", "description": "Applies a targeted edit to a local file.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "search_string": {"type": "string"}, "replace_string": {"type": "string"}}, "required": ["filepath", "search_string", "replace_string"]}}},
            {"type": "function", "function": {"name": "list_directory", "description": "Lists files in a path.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "update_longterm_memory", "description": "Appends facts to MEMORY.md.", "parameters": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}}},
            {"type": "function", "function": {"name": "cron_add", "description": "Add task. 'schedule' format: 'oneshot <sec>' or 'interval <sec>'.", "parameters": {"type": "object", "properties": {"schedule": {"type": "string"}, "task_description": {"type": "string"}}, "required": ["schedule", "task_description"]}}},
            {"type": "function", "function": {"name": "cron_list", "description": "List jobs.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "cron_remove", "description": "Remove job.", "parameters": {"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]}}},
            {"type": "function", "function": {"name": "clear_vram", "description": "Frees up VRAM.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "send_telegram_media", "description": "Sends ComfyUI media to Telegram.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "caption": {"type": "string"}}, "required": ["filename"]}}},
            {"type": "function", "function": {"name": "send_telegram_message", "description": "Sends SMS to user.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}}},
            {"type": "function", "function": {"name": "search_vision_history", "description": "YOUR LIVE EYES. Searches the real-time background vision daemon to see what is CURRENTLY on the user's screen, or past activity. Use this IMMEDIATELY whenever the user asks 'what am I looking at', 'what is on my screen', or checks their current activity.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Use 'latest' to get the live feed, or a specific topic to search the past."}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "check_python_dependencies", "description": "Checks if specific Python packages are installed before attempting to use or install them.", "parameters": {"type": "object", "properties": {"packages": {"type": "array", "items": {"type": "string"}, "description": "List of pip package names to check (e.g. ['fastapi', 'uvicorn'])"}}, "required": ["packages"]}}},
            {"type": "function", "function": {"name": "deploy_new_mcp", "description": "Writes, launches, and registers a new Python MCP server. IMPORTANT: The code MUST include a FastAPI server running on the specified port with /messages and /sse endpoints.", "parameters": {"type": "object", "properties": {"server_name": {"type": "string"}, "port": {"type": "integer"}, "python_code": {"type": "string"}}, "required": ["server_name", "port", "python_code"]}}}
        ]

        if self.sub_agents_enabled:
            self.native_tools.append({
                "type": "function", 
                "function": {
                    "name": "delegate_task", 
                    "description": "Spin up sub-agent for heavy research or coding. Instructions MUST include target filename if applicable.", 
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "agent_type": {"type": "string", "enum": ["web_researcher", "python_coder"]}, 
                            "instructions": {"type": "string"}
                        }, 
                        "required": ["agent_type", "instructions"]
                    }
                }
            })

    def load_settings(self):
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def setup_openclaw_fs(self):
        os.makedirs(self.mem_dir, exist_ok=True)
        for f, content in [(self.heartbeat_file, "Check cron-inbox.md."), (self.long_term_mem, "# KOKO LTM\n"), (self.cron_inbox, "")]:
            if not os.path.exists(f):
                open(f, "w", encoding="utf-8").write(content)
        if not os.path.exists(self.cron_db):
            json.dump({"jobs": []}, open(self.cron_db, "w", encoding="utf-8"))

    def initialize_agent_mind(self):
        prompt = (
            "You are Koko, the Director Agent of an autonomous OS. "
            f"You are currently operating in {self.os_mode} mode. "
            "CRITICAL RULE: You must ALWAYS speak to the user, acknowledge their request, and briefly explain your plan BEFORE invoking any tools. Never execute a tool silently. "
            "CRITICAL RULE: Before installing any Python packages or writing code that requires third-party libraries, you MUST use the `check_python_dependencies` tool to verify if they are already installed. Do not blindly install packages. "
            # ... keep the rest of your prompt intact ...
            "You have a real-time Passive Vision daemon running. If the user asks what is on their screen, YOU CAN SEE IT by using the search_vision_history tool with the query 'latest'. "
            "Always use <think> tags to reason before acting. "
            # ... keep the rest of your prompt ...
            "Actively use clear_vram to manage system load. "
            "If you need complex coding, website generation, or deep research, you MUST use delegate_task to assign it to a sub-agent so your context remains pristine. "
            "For Remote Telegram context, reply plain text/markdown only, no HTML/tags. Use standard emoji. "
            "If a cron job wakes you up, you MUST use send_telegram_message to alert the user on their phone."
        )
        try:
            with open(self.long_term_mem, 'r', encoding='utf-8') as f:
                ltm_data = f.read()
            prompt += f"\n\n=== LONG TERM MEMORY ===\n{ltm_data}"
        except:
            pass
        self.chat_history = [{"role": "system", "content": prompt}]
        
        try:
            if os.path.exists(self.context_cache_file):
                with open(self.context_cache_file, "r", encoding="utf-8") as f:
                    saved_history = json.load(f)
                    self.chat_history.extend(saved_history[-10:])
        except:
            pass

    def save_context_cache(self):
        try:
            cache_data = []
            for msg in self.chat_history[1:]:
                msg_copy = msg.copy()
                if isinstance(msg_copy.get("content"), list):
                    clean_content = []
                    for item in msg_copy["content"]:
                        if item.get("type") == "image_url":
                            clean_content.append({"type": "text", "text": "[Image data cleared to save cache memory]"})
                        else:
                            clean_content.append(item)
                    msg_copy["content"] = clean_content
                cache_data.append(msg_copy)
                
            with open(self.context_cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
        except:
            pass

    def write_daily_log(self, text):
        today = datetime.now().strftime("%Y-%m-%d")
        with open(os.path.join(self.mem_dir, f"{today}.md"), "a", encoding="utf-8") as f: 
            f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] {text}")

    def compose(self) -> ComposeResult:
        yield Static(KOKO_HEADER, id="header_logo")
        with Horizontal(id="main_layout"):
            with Vertical(id="sidebar"):
                yield Static("📁 PROJECT SCOPE & FILES", id="sidebar_title")
                yield Static("No active project loaded.\n\nType in Plan Mode to define scopes, map out directories, and gather references.", id="project_tree")
            with Vertical(id="chat_area"):
                yield VerticalScroll(id="chat_log")
                with Vertical(id="input_container"):
                    yield ChatTextArea(id="koko_input", show_line_numbers=False)
                    yield Static(f"{self.os_mode}:", id="mode_indicator", classes="build_mode")
        yield Footer()

    def get_metrics_bar(self, tokens, start_time, end_time):
        duration = max(0.001, end_time - start_time)
        tps = tokens / duration
        self.total_tokens += tokens
        ctx_pct = min(100.0, (self.total_tokens / self.context_limit) * 100)
        filled = min(20, max(0, int((self.total_tokens / self.context_limit) * 20)))
        bar = "█" * filled + "░" * (20 - filled)
        return f"\n\n[dim]{tokens} tkns  {tps:.1f} t/s  {duration:.2f}s  CTX: \\[[#238636]{bar}[/]] {ctx_pct:.1f}%[/]"

    async def on_mount(self) -> None:
        await self.action_refresh_mcp()
        tel_status = "Syncing" if self.tg_enabled and self.tg_token else "Disabled"
        sub_status = "Active" if self.sub_agents_enabled else "Off"
        vision_status = "Available" if self.vision_collection else "Offline"
        
        await self.append_to_chat(f"Initializing Koko OS Shell...", classes="msg-sys")
        await self.append_to_chat(f"Active Engine: {self.active_engine.upper()}", classes="msg-sys")
        await self.append_to_chat(f"Telecom: {tel_status} | Sub-Agents: {sub_status} | Vision DB: {vision_status}", classes="msg-sys")
        
        # --- WHISPER STARTUP DIAGNOSTIC ---
        if getattr(self, 'whisper_model', None):
            await self.append_to_chat("🎙️ Voice Engine: ONLINE (Press F8 to talk)", classes="msg-sys")
        else:
            await self.append_to_chat("🔇 Voice Engine: OFFLINE (Type /voice enable to load)", classes="msg-error")
        
        cache_count = len(self.chat_history) - 1
        if cache_count > 0:
            await self.append_to_chat(f"Loaded {cache_count} recent messages from memory cache.", classes="msg-sys")
        
        await self.append_to_chat(f"Ready. Type /help or /models for commands.", classes="msg-sys")
        
        if self.settings.get("gateway", {}).get("enabled", False):
            self.set_interval(self.settings.get("gateway", {}).get("tick_rate_seconds", 60), self.gateway_tick)
        if self.tg_enabled and self.tg_token:
            self.set_interval(3.0, self.telegram_tick)
        
        # Fast tick for passive observer, interval logic handled inside
        self.set_interval(1.0, self.passive_vision_loop)
            
        self.query_one("#koko_input").focus()

    def action_abort(self) -> None:
        self.abort_flag = True

    def action_request_quit(self) -> None:
        def check_quit(quit_confirmed: bool):
            if quit_confirmed:
                self.abort_flag = True 
                self.exit() 
                import threading
                threading.Timer(1.5, lambda: os._exit(0)).start() 
        self.push_screen(QuitModal(), check_quit)

    def action_command_settings(self) -> None:
        asyncio.create_task(self.process_command("/settings", datetime.now().strftime("%I:%M %p")))

    def action_toggle_mode(self) -> None:
        if self.os_mode == "BUILD":
            self.os_mode = "PLAN"
            self.query_one("#mode_indicator").update("PLAN:")
            self.query_one("#mode_indicator").remove_class("build_mode")
            self.query_one("#mode_indicator").add_class("plan_mode")
            self.query_one("#sidebar").add_class("active")
            self.chat_history[0]["content"] = self.chat_history[0]["content"].replace("BUILD mode", "PLAN mode")
            asyncio.create_task(self.append_to_chat(" > Switched to PLAN mode. Sidebar active.", classes="msg-sys"))
        else:
            self.os_mode = "BUILD"
            self.query_one("#mode_indicator").update("BUILD:")
            self.query_one("#mode_indicator").remove_class("plan_mode")
            self.query_one("#mode_indicator").add_class("build_mode")
            self.query_one("#sidebar").remove_class("active")
            self.chat_history[0]["content"] = self.chat_history[0]["content"].replace("PLAN mode", "BUILD mode")
            asyncio.create_task(self.append_to_chat(" > Switched to BUILD mode. Executing allowed.", classes="msg-sys"))

    def action_toggle_engine(self) -> None:
        if self.active_engine == "local":
            if not self.gemini_key or self.gemini_key == "YOUR_GEMINI_API_KEY":
                asyncio.create_task(self.append_to_chat("❌ Cannot switch to Gemini: API Key missing in Settings (CTRL+S).", classes="msg-error"))
                return
            if not self.gemini_client:
                self.gemini_client = AsyncOpenAI(base_url=self.gemini_base, api_key=self.gemini_key)
            self.active_engine = "gemini"
        else:
            self.active_engine = "local"
            
        self.settings["active_engine"] = self.active_engine
        try:
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except: pass
        
        asyncio.create_task(self.append_to_chat(f"🚀 Core Engine Switched: [{self.active_engine.upper()}]", classes="msg-sys"))

    async def action_paste_image(self) -> None:
        if self.is_processing: return
        try:
            from PIL import ImageGrab, Image
            import io
        except ImportError:
            await self.append_to_chat("System Error: 'Pillow' library is required to paste images. Run: pip install Pillow", classes="msg-error")
            return

        try:
            img = ImageGrab.grabclipboard()
        except Exception as e:
            await self.append_to_chat(f"Clipboard Error: {e}", classes="msg-error")
            return

        if img is None:
            await self.append_to_chat("No image found in clipboard. Take a screenshot first!", classes="msg-error")
            return

        if isinstance(img, list):
            file_path = img[0]
            if str(file_path).lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                try:
                    img = Image.open(file_path)
                except Exception as e:
                    await self.append_to_chat(f"Failed to open image file: {e}", classes="msg-error")
                    return
            else:
                await self.append_to_chat("Clipboard contains a file, but not a recognized image format.", classes="msg-error")
                return

        os.makedirs("downloads", exist_ok=True)
        filename = f"downloads/clip_{int(time.time())}.jpg"
        
        try:
            img = img.convert('RGB')
            img.save(filename, "JPEG", quality=90)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            b64_img = base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            await self.append_to_chat(f"Image processing error: {e}", classes="msg-error")
            return

        user_input_widget = self.query_one("#koko_input")
        user_text = user_input_widget.text.strip()
        try:
            user_input_widget.text = ""
            user_input_widget.cursor_location = (0, 0)
        except:
            pass

        text_part = user_text if user_text else "Please analyze this attached image."
        content_payload = [
            {"type": "text", "text": text_part},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
        ]

        display_text = f"{text_part} [Attached: {filename}]"
        timestamp = datetime.now().strftime("%I:%M %p")
        self.write_daily_log(f"USER: {display_text}")
        await self.append_to_chat(f"user@kokocode:~$ {display_text}", classes="msg-user")
        self.chat_history.append({"role": "user", "content": content_payload})
        asyncio.create_task(self.process_ai(timestamp, is_background=False))

    # 👇 PASTE STEP 4 HERE 👇
    def audio_callback(self, indata, frames, time, status):
        # This silently captures audio frames while the mic is open
        if self.is_recording:
            self.audio_frames.append(indata.copy())

    async def action_toggle_mic(self) -> None:
        if self.is_processing:
            return

        # 👇 PASTE SAFETY GUARD HERE 👇
        if not getattr(self, 'whisper_model', None):
            await self.append_to_chat("❌ Voice module is currently UNLOADED. Type '/voice enable' to load it.", classes="msg-error")
            return
        # 👆 PASTE SAFETY GUARD HERE 👆

        if not self.is_recording:
            # 🟢 OPEN MIC
            self.is_recording = True
            self.audio_frames = []
            self.audio_stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32', callback=self.audio_callback)
            self.audio_stream.start()
            await self.append_to_chat("🎙️ Voice module ENABLED. Press F8 to use.", classes="msg-sys")
        else:
            # 🔴 CLOSE MIC & TRANSCRIBE
            self.is_recording = False
            self.audio_stream.stop()
            self.audio_stream.close()
            
            # Temporary UI update while thinking
            loading_widget = await self.append_to_chat("⏳ Transcribing audio...", classes="msg-sys")

            # Process audio in a background thread to prevent UI freezing
            def transcribe_audio():
                try:
                    if not self.audio_frames: return ""
                    # Flatten the audio chunks into a single array for Whisper
                    audio_data = np.concatenate(self.audio_frames, axis=0).flatten()
                    segments, _ = self.whisper_model.transcribe(audio_data, beam_size=5)
                    return "".join([segment.text for segment in segments]).strip()
                except Exception as e:
                    self.write_daily_log(f"Whisper Error: {e}")
                    return ""

            loop = asyncio.get_running_loop()
            transcription = await loop.run_in_executor(None, transcribe_audio)
            
            # Remove the "Transcribing..." text
            await loading_widget.remove()

            if transcription:
                # 🚀 FIRE IT INTO KOKO'S BRAIN
                timestamp = datetime.now().strftime("%I:%M %p")
                self.write_daily_log(f"USER (VOICE): {transcription}")
                await self.append_to_chat(f"user@kokocode:~$ 🎤 {transcription}", classes="msg-user")
                self.chat_history.append({"role": "user", "content": transcription})
                asyncio.create_task(self.process_ai(timestamp, is_background=False))
            else:
                await self.append_to_chat("❌ Could not hear anything or transcription failed.", classes="msg-error")
    # 👆 PASTE STEP 4 HERE 👆

    async def append_to_chat(self, renderable, classes="msg-sys"):
        log = self.query_one("#chat_log")
        is_user = classes == "msg-user"
        should_scroll = is_user or (log.scroll_y >= log.max_scroll_y - 3)
        if isinstance(renderable, str):
            renderable = emoji.emojize(renderable, language='alias')
        widget = Static(renderable, classes=classes)
        await log.mount(widget)
        if should_scroll:
            log.scroll_end(animate=False)
        return widget

    async def passive_vision_loop(self):
        if not self.passive_enabled or self.is_processing or not self.vision_collection: return
        now = time.time()
        if now - self.last_passive_time < self.passive_interval: return
        self.last_passive_time = now
        
        try:
            from PIL import ImageGrab
            import io
            import re
            img = ImageGrab.grab()
            
            img_bytes = img.tobytes()
            current_hash = hashlib.md5(img_bytes).hexdigest()
            if current_hash == getattr(self, "last_screenshot_hash", None): return
            self.last_screenshot_hash = current_hash
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=60)
            b64_img = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # 🚀 Add a strict system prompt to discourage long thinking
            payload = [
                {"role": "system", "content": "You are a vision analysis sub-agent. Describe the user's screen objectively. Do not use think tags. Just provide the description."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe the active window and what the user is currently doing on this screen. Be concise and factual."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                ]}
            ]
            
            # 🚀 FIX 1: Increase max_tokens to 1024 so it doesn't get cut off mid-thought
            response = await self.local_client.chat.completions.create(
                model=self.model_name,
                messages=payload,
                max_tokens=1024,
                temperature=0.2
            )
            
            raw_description = response.choices[0].message.content.strip()
            
            # 🚀 FIX 2: Strip out the <think> tags so Koko doesn't internalize the memory
            description = re.sub(r'<think>.*?</think>', '', raw_description, flags=re.DOTALL).strip()
            
            # Failsafe: If the model ONLY output a thought and nothing else
            if not description and raw_description:
                description = raw_description.replace("<think>", "").replace("</think>", "").strip()
            
            if not description:
                description = "[Vision Model returned an empty string. The model may have rejected the image payload.]"
            
            self.latest_vision_desc = description
            self.latest_vision_time = datetime.now().strftime("%I:%M:%S %p")
            
            mem_id = f"vis_{int(time.time())}"
            timestamp = datetime.now().isoformat()
            self.vision_collection.add(
                documents=[description],
                metadatas=[{"timestamp": timestamp}],
                ids=[mem_id]
            )
            self.write_daily_log(f"VIS: {description}")
        except Exception as e:
            self.write_daily_log(f"PASSIVE VISION ERROR: {str(e)}")

    async def telegram_tick(self):
        if self.is_processing: return
        try:
            url = f"https://api.telegram.org/bot{self.tg_token}/getUpdates"
            params = {"offset": self.tg_offset, "timeout": 2}
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url, params=params)
                data = res.json()
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        self.tg_offset = update["update_id"] + 1
                        with open(self.tg_offset_file, "w") as f:
                            f.write(str(self.tg_offset))
                        
                        msg = update.get("message", {})
                        chat_id = str(msg.get("chat", {}).get("id", ""))
                        text = msg.get("text", "")
                        
                        if chat_id in self.tg_chats:
                            timestamp = datetime.now().strftime("%I:%M %p")
                            if text and text.strip().lower() == "/flush":
                                self.chat_history = [{"role": "system", "content": self.chat_history[0]["content"]}]
                                self.total_tokens = 0
                                self.save_context_cache()
                                await self.append_to_chat(f"remote@{chat_id}:~$ {text}", classes="msg-remote")
                                await self.append_to_chat("Remote Context Flush Triggered.", classes="msg-sys")
                                async with httpx.AsyncClient(timeout=10.0) as flush_client:
                                    await flush_client.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", json={"chat_id": chat_id, "text": "✅ Koko OS Short-term memory flushed."})
                                continue

                            content_payload = None
                            display_text = ""

                            if "photo" in msg:
                                file_id = msg["photo"][-1]["file_id"]
                                caption = msg.get("caption", "View attachment.")
                                display_text = f"[Remote Image]: {caption}"
                                self.write_daily_log(f"TG IN (IMG): {caption}")
                                try:
                                    file_url = f"https://api.telegram.org/bot{self.tg_token}/getFile?file_id={file_id}"
                                    async with httpx.AsyncClient(timeout=10.0) as fetch_client:
                                        file_res = await fetch_client.get(file_url)
                                        file_path = file_res.json()["result"]["file_path"]
                                        dl_url = f"https://api.telegram.org/file/bot{self.tg_token}/{file_path}"
                                        img_res = await fetch_client.get(dl_url)
                                        img_bytes = img_res.content
                                    os.makedirs("downloads", exist_ok=True)
                                    filename = f"downloads/tg_{int(time.time())}.jpg"
                                    with open(filename, "wb") as f:
                                        f.write(img_bytes)
                                    b64_img = base64.b64encode(img_bytes).decode('utf-8')
                                    content_payload = [
                                        {"type": "text", "text": f"[From Telecom]: {caption}\n(Note: Saved locally as `{filename}`.)"},
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                                    ]
                                    await self.append_to_chat(f"Attachment saved to {filename}", classes="msg-sys")
                                except:
                                    pass
                            elif text:
                                display_text = text
                                content_payload = f"[From Telecom]: {text}\n(Note: Text only.)"
                                self.write_daily_log(f"TG IN: {text}")
                                
                            if content_payload:
                                await self.append_to_chat(f"remote@{chat_id}:~$ {display_text}", classes="msg-remote")
                                self.chat_history.append({"role": "user", "content": content_payload})
                                asyncio.create_task(self.process_ai(timestamp, is_background=True, remote_context={"platform": "telegram", "chat_id": chat_id}))
        except:
            pass

    async def gateway_tick(self):
        if self.is_processing: return
        fired_tasks = []
        now = time.time()
        try:
            with open(self.cron_db, "r", encoding="utf-8") as f:
                db = json.load(f)
            for job in db.get("jobs", []):
                if now >= job["next_run"]:
                    fired_tasks.append(job["task"])
                    if job["type"] == "interval":
                        job["next_run"] = now + job["interval"]
                    else:
                        job["status"] = "completed"
            
            active_jobs = [j for j in db.get("jobs", []) if j.get("status") != "completed"]
            with open(self.cron_db, "w", encoding="utf-8") as f:
                json.dump({"jobs": active_jobs}, f, indent=2)
            
            if fired_tasks:
                with open(self.cron_inbox, "a", encoding="utf-8") as f:
                    for t in fired_tasks:
                        f.write(f"- [CRON]: {t}\n")
                
                hb = open(self.heartbeat_file, "r", encoding="utf-8").read()
                inbox = open(self.cron_inbox, "r", encoding="utf-8").read()
                
                system_ping = f"=== WAKEUP ===\nHB:\n{hb}\n\nInbox:\n{inbox}\nReview & act. Headless thread. use send_telegram_message if needed. reply exactly: 'heartbeat' if no action."
                self.chat_history.append({"role": "user", "content": system_ping})
                asyncio.create_task(self.process_ai(datetime.now().strftime("%I:%M %p"), is_background=True))
                with open(self.cron_inbox, "w", encoding="utf-8") as f:
                    f.write("")
        except:
            pass

    async def action_refresh_mcp(self):
        await self.mcp.discover_tools()
        await self.append_to_chat("System tools synchronized.", classes="msg-sys")

    async def execute_tool(self, name, args):
        """Central tool dispatch with proper error handling and logging."""
        start_time = time.time()
        path = os.path.abspath(os.path.expanduser(args.get("path", args.get("filepath", ""))))
        
        try:
            result = await self._execute_tool_impl(name, args, path)
            elapsed = time.time() - start_time
            logger.info(f"Tool '{name}' executed successfully in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Tool '{name}' failed after {elapsed:.2f}s: {e}")
            return f"Error executing '{name}': {str(e)}"

    async def _execute_tool_impl(self, name, args, path):
        """Internal tool implementation - returns result or raises exception."""
        if name == "clear_vram":
            async with httpx.AsyncClient(timeout=3.0) as client:
                try: await client.post("http://127.0.0.1:8080/slots/0?action=clear")
                except: pass
                try: await client.post("http://127.0.0.1:8188/free", json={"unload_models": True, "free_memory": True})
                except: pass
            return "VRAM cleared."
        elif name == "search_vision_history":
            try:
                if not self.vision_collection: return "Vision DB offline."
                query = args.get("query", "")
                
                # 🚀 BYPASS: If she wants the live screen, give her the volatile memory immediately
                if "latest" in query.lower() or "current" in query.lower() or "now" in query.lower() or "screen" in query.lower():
                    if hasattr(self, "latest_vision_desc") and self.latest_vision_desc:
                        return f"LIVE SCREEN FEED [{self.latest_vision_time}]: {self.latest_vision_desc}"
                    else:
                        return "Live feed is currently capturing... please wait a few seconds and try again."

                # Otherwise, do the standard semantic search for past history
                results = self.vision_collection.query(query_texts=[query], n_results=3)
                if not results['documents'] or not results['documents'][0]: return "No visual memories match."
                
                res_text = "Visual Memory Hits:\n"
                for i in range(len(results['documents'][0])):
                    date = results['metadatas'][0][i].get('timestamp', '')[:19]
                    doc = results['documents'][0][i]
                    res_text += f"[{date}]: {doc}\n"
                return res_text
            except Exception as e: return f"Vision search error: {e}"
        elif name == "deploy_new_mcp":
            try:
                server_name = args.get("server_name", "new_mcp")
                port = args.get("port", 3050)
                code = args.get("python_code", "")
                
                os.makedirs("mcp_servers", exist_ok=True)
                file_path = os.path.join("mcp_servers", f"{server_name}.py")
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)
                
                subprocess.Popen([sys.executable, file_path], cwd=os.getcwd())
                
                new_url = f"http://127.0.0.1:{port}/messages"
                if new_url not in self.settings.get("mcp_servers", []):
                    self.settings.setdefault("mcp_servers", []).append(new_url)
                    with open("settings.json", "w", encoding="utf-8") as f:
                        json.dump(self.settings, f, indent=4)
                
                self.mcp.servers.append(new_url)
                await self.action_refresh_mcp()
                return f"Deployed {server_name} on port {port}. Server added to active MCP pool and tools synced."
            except Exception as e: return f"Deployment failed: {e}"
        elif name == "send_telegram_media":
            if not self.tg_token or not self.tg_chats: return "Error: Telecom offline."
            try:
                filename = args.get("filename", "")
                caption = args.get("caption", "")
                comfy_url = f"http://127.0.0.1:8188/view?filename={filename}&type=output"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    media_res = await client.get(comfy_url)
                    media_bytes = media_res.content
                    if filename.lower().endswith(('.wav', '.mp3')):
                        files = {"audio": (filename, media_bytes)}
                        tg_url = f"https://api.telegram.org/bot{self.tg_token}/sendAudio"
                    else:
                        files = {"photo": (filename, media_bytes)}
                        tg_url = f"https://api.telegram.org/bot{self.tg_token}/sendPhoto"
                    await client.post(tg_url, data={"chat_id": self.tg_chats[0], "caption": caption}, files=files)
                return f"transmitted {filename}."
            except Exception as e: return f"Transmit error: {e}"
        elif name == "send_telegram_message":
            if not self.tg_token or not self.tg_chats: return "Error: Telecom offline."
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", json={"chat_id": self.tg_chats[0], "text": args.get("message", "")})
                return "SMS sent."
            except Exception as e: return f"SMS error: {e}"
        elif name == "delegate_task":
            try:
                task_description = args.get("instructions", "No instructions provided.")
                agent_type = args.get("agent_type", "python_coder")
                
                main_client = self.gemini_client if self.active_engine == "gemini" else self.local_client
                main_model = self.gemini_model if self.active_engine == "gemini" else self.model_name
                log_scroll = self.query_one("#chat_log")
                
                if agent_type == "web_researcher":
                    swarm_type = "Research"
                    agent_1_role = "Lead Researcher"
                    agent_1_system = "You are the Lead Researcher. Find highly accurate, detailed information. Synthesize complex topics clearly."
                    agent_2_role = "Fact-Checking Editor"
                    agent_2_system = "You are the Fact-Checking Editor. Review the research for logical fallacies. If it needs work, explain why and end with 'REJECTED'. If perfect, end with 'APPROVED'."
                else:
                    swarm_type = "Coding"
                    agent_1_role = "Lead Engineer"
                    agent_1_system = "You are the Lead Engineer. Write highly optimized, beautiful code. CRITICAL INSTRUCTION: You must provide the full, complete code block. Do not condense or truncate."
                    agent_2_role = "QA Reviewer"
                    agent_2_system = "You are the QA Reviewer. Review the code. If it needs work, provide detailed feedback and end with EXACTLY 'REJECTED'. If flawless, end with EXACTLY 'APPROVED'."
                
                history = [{"role": "system", "content": agent_1_system}, {"role": "user", "content": task_description}]
                max_loops = 3
                current_loop = 1
                draft_output = ""
                
                await self.append_to_chat(f"[{swarm_type} Swarm Activated]: Powered by {main_model}", classes="msg-sys")
                
                while current_loop <= max_loops:
                    if getattr(self, "abort_flag", False): return "SWARM ABORTED BY USER."
                    await self.append_to_chat(f"\n--- Iteration {current_loop}/{max_loops} ---", classes="msg-sys")
                    stream_widget = await self.append_to_chat(f"{agent_1_role}> ...", classes="msg-sys")
                    
                    resp = await main_client.chat.completions.create(model=main_model, messages=history, temperature=0.2, stream=True)
                    draft_output = ""
                    async for chunk in resp:
                        if getattr(self, "abort_flag", False): return "SWARM ABORTED BY USER."
                        if chunk.choices and chunk.choices[0].delta.content:
                            draft_output += chunk.choices[0].delta.content
                            should_scroll = log_scroll.scroll_y >= (log_scroll.max_scroll_y - 3)
                            prefix = Text(f"{agent_1_role}> ", style="#d2a8ff bold")
                            md = Markdown(emoji.emojize(draft_output + " ▌", language='alias'))
                            stream_widget.update(Group(prefix, md))
                            if should_scroll: log_scroll.scroll_end(animate=False)
                            
                    prefix = Text(f"{agent_1_role}> ", style="#d2a8ff bold")
                    md = Markdown(emoji.emojize(draft_output, language='alias'))
                    stream_widget.update(Group(prefix, md))

                    review_widget = await self.append_to_chat(f"\n{agent_2_role}> Analyzing...", classes="msg-sys")
                    agent_2_history = [{"role": "system", "content": agent_2_system}, {"role": "user", "content": f"Review this output based on the original task: '{task_description}'.\n\nOUTPUT:\n{draft_output}"}]
                    agent_2_response = await main_client.chat.completions.create(model=main_model, messages=agent_2_history, temperature=0.1, stream=True)
                    feedback = ""
                    async for chunk in agent_2_response:
                        if getattr(self, "abort_flag", False): return "SWARM ABORTED BY USER."
                        if chunk.choices and chunk.choices[0].delta.content:
                            feedback += chunk.choices[0].delta.content
                            should_scroll = log_scroll.scroll_y >= (log_scroll.max_scroll_y - 3)
                            prefix = Text(f"{agent_2_role}> ", style="#ff7b72 bold")
                            md = Markdown(emoji.emojize(feedback + " ▌", language='alias'))
                            review_widget.update(Group(prefix, md))
                            if should_scroll: log_scroll.scroll_end(animate=False)
                            
                    prefix = Text(f"{agent_2_role}> ", style="#ff7b72 bold")
                    md = Markdown(emoji.emojize(feedback, language='alias'))
                    review_widget.update(Group(prefix, md))
                    
                    if "APPROVED" in feedback.upper():
                        await self.append_to_chat(f"\n[{agent_2_role} APPROVED] Consensus reached.", classes="msg-sys")
                        return f"SWARM CONSENSUS REACHED.\n\nCRITICAL INSTRUCTION FOR DIRECTOR: You must now IMMEDIATELY use the `write_local_file` tool to save the following code to the user's requested filename. Do not ask for permission, just save it.\n\nOutput:\n\n{draft_output}"
                    else:
                        await self.append_to_chat(f"\n[{agent_2_role} REJECTED] Sending back to {agent_1_role} for revisions.", classes="msg-error")
                        history = [
                            {"role": "system", "content": agent_1_system}, 
                            {"role": "user", "content": task_description}, 
                            {"role": "assistant", "content": draft_output},
                            {"role": "user", "content": f"{agent_2_role.upper()} REJECTED YOUR DRAFT. Address these issues and rewrite the file completely:\n{feedback}"}
                        ]
                        current_loop += 1
                return f"SWARM TIMEOUT. Best attempt:\n{draft_output}\n\nUnresolved Feedback:\n{feedback}\n\nCRITICAL INSTRUCTION FOR DIRECTOR: Use the `write_local_file` tool to save this best attempt."
            except Exception as e: return f"SWARM SYSTEM FAILURE: {str(e)}"
        elif name == "read_local_file":
            try: return open(path, 'r', encoding='utf-8').read()
            except Exception as e: return f"Error: {e}"
        elif name == "write_local_file":
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f: f.write(args.get("content", ""))
                return f"Wrote {path}"
            except Exception as e: return f"Error: {e}"
        elif name == "edit_local_file":
            try:
                target = os.path.abspath(os.path.expanduser(args.get("filepath", "")))
                search_str = args.get("search_string", "")
                replace_str = args.get("replace_string", "")
                if not os.path.exists(target): return f"Error: File {target} not found."
                content = open(target, 'r', encoding='utf-8').read()
                if search_str not in content: return f"Error: Exact search string not found."
                new_content = content.replace(search_str, replace_str, 1)
                open(target, 'w', encoding='utf-8').write(new_content)
                return f"Successfully patched {target}."
            except Exception as e: return f"Error: {e}"
        elif name == "list_directory":
            try:
                items = os.listdir(path)
                dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
                files = [f for f in items if os.path.isfile(os.path.join(path, f))]
                return f"Folders: {', '.join(dirs[:20])}\nFiles: {', '.join(files[:50])}"
            except Exception as e: return f"Error: {e}"
        elif name == "search_codebase":
            keyword = args.get("keyword", "")
            matches = []
            try:
                for root, dirs, files in os.walk(path):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '__pycache__')]
                    for file in files:
                        try:
                            for i, line in enumerate(open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore')):
                                if keyword.lower() in line.lower():
                                    matches.append(f"{file} (L{i+1}): {line.strip()[:80]}")
                                    if len(matches) > 30: return "\n".join(matches) + "\n... [Truncated]"
                        except: pass
                return "\n".join(matches) if matches else "No matches."
            except Exception as e: return f"Error: {e}"
        elif name == "update_longterm_memory":
            try:
                with open(self.long_term_mem, "a", encoding="utf-8") as f: f.write(f"\n- {args.get('fact', '')}")
                return "Memory updated."
            except Exception as e: return f"Error: {e}"
        elif name == "cron_add":
            try:
                sched, task = args.get("schedule", ""), args.get("task_description", "")
                with open(self.cron_db, "r", encoding="utf-8") as f: db = json.load(f)
                sec = int(sched.split(" ")[1])
                db["jobs"].append({"id": str(uuid.uuid4())[:8], "type": "interval" if "interval" in sched else "oneshot", "interval": sec if "interval" in sched else None, "next_run": time.time() + sec, "task": task})
                with open(self.cron_db, "w", encoding="utf-8") as f: json.dump(db, f, indent=2)
                return "Job added."
            except: return "Format error."
        elif name == "cron_list":
            try:
                with open(self.cron_db, "r", encoding="utf-8") as f: db = json.load(f)
                return json.dumps(db["jobs"], indent=2) or "No jobs."
            except: return "Error."
        elif name == "cron_remove":
            try:
                with open(self.cron_db, "r", encoding="utf-8") as f: db = json.load(f)
                db["jobs"] = [j for j in db["jobs"] if j["id"] != args.get("job_id", "")]
                with open(self.cron_db, "w", encoding="utf-8") as f: json.dump(db, f, indent=2)
                return "Job removed."
            except: return "Error."
        elif name == "check_python_dependencies":
            try:
                import subprocess
                packages = args.get("packages", [])
                results = []
                for pkg in packages:
                    # Uses the exact Python environment Koko is currently running in
                    req = subprocess.run([sys.executable, "-m", "pip", "show", pkg], capture_output=True, text=True)
                    if req.returncode == 0:
                        results.append(f"✅ [INSTALLED]: {pkg}")
                    else:
                        results.append(f"❌ [MISSING]: {pkg}")
                return "\n".join(results)
            except Exception as e: return f"Dependency check error: {e}"
        else:
            url = self.mcp.tool_directory.get(name)
            if not url: return f"MCP Error: Tool '{name}' not found."
            try:
                async def _call_mcp():
                    async with httpx.AsyncClient(timeout=300.0) as client:
                        res = await client.post(url, json={"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":name,"arguments":args}})
                        data = res.json()
                        return data["result"]["content"][0]["text"]
                
                result = await retry_on_failure(_call_mcp, max_retries=2, delay=1.5)
                logger.info(f"MCP tool '{name}' executed successfully in {time.time()-start_time:.2f}s")
                return result
            except Exception as e: 
                logger.error(f"MCP tool '{name}' failed after retries: {e}")
                return f"MCP Error: Failed to execute '{name}'. Details: {repr(e)}"
            
        # Log execution time for all tools
        logger.info(f"Tool '{name}' executed in {time.time()-start_time:.2f}s")

    async def execute_tool(self, name, args):  # Fallback - should not reach here due to above patches
        """DEPRECATED: Use the patched version above."""
        pass
            
            
            

    async def process_command(self, user_text, timestamp):
        parts = user_text.split()
        cmd = parts[0].lower()
        log = self.query_one("#chat_log")

        await self.append_to_chat(f"user@kokocode:~$ {user_text}", classes="msg-user")

        if cmd == "/help":
            await self.append_to_chat("Commands: /settings, /models, /mcp [add|remove|list], /passive [on|off|seconds], /clear, /flush, /vram", classes="msg-sys")
            
        elif cmd == "/models":
            msg = f"🧠 Available AI Engines:\n" \
                  f"1. [LOCAL] Model: {self.model_name} (Port 8080)\n" \
                  f"2. [GEMINI] Model: {self.gemini_model} (Cloud API)\n" \
                  f"\nCurrently Active: [{self.active_engine.upper()}] - Press F4 to toggle."
            await self.append_to_chat(msg, classes="msg-sys")

        elif cmd == "/settings":
            def check_settings(new_settings):
                if new_settings:
                    with open("settings.json", "w", encoding="utf-8") as f:
                        json.dump(new_settings, f, indent=4)
                    asyncio.create_task(self.append_to_chat("Configuration Updated. Restart recommended to apply LLM changes.", classes="msg-sys"))
            self.push_screen(SettingsModal(self.settings), check_settings)

        elif cmd == "/passive":
            if len(parts) == 1:
                status = "ON" if getattr(self, "passive_enabled", False) else "OFF"
                await self.append_to_chat(f"Passive Vision: {status} | Interval: {getattr(self, 'passive_interval', 60)}s.", classes="msg-sys")
            else:
                arg = parts[1].lower()
                if arg == "on":
                    self.passive_enabled = True
                    await self.append_to_chat("👁️ Passive Vision Engine ONLINE. Monitoring screen...", classes="msg-sys")
                elif arg == "off":
                    self.passive_enabled = False
                    await self.append_to_chat("👁️ Passive Vision Engine OFFLINE.", classes="msg-sys")
                elif arg.isdigit():
                    self.passive_interval = int(arg)
                    await self.append_to_chat(f"👁️ Passive interval set to {self.passive_interval} seconds.", classes="msg-sys")
                else:
                    await self.append_to_chat("Usage: /passive [on|off|seconds]", classes="msg-error")

        elif cmd == "/clear":
            for child in log.children: await child.remove()
            await self.append_to_chat("Buffer cleared.", classes="msg-sys")

        elif cmd == "/flush":
            self.chat_history = [{"role": "system", "content": self.chat_history[0]["content"]}]
            self.total_tokens = 0
            self.save_context_cache()
            await self.append_to_chat("Short-term memory reset.", classes="msg-sys")

        elif cmd == "/vram":
            await self.append_to_chat("Manual VRAM flush requested...", classes="msg-sys")
            result = await self.execute_tool("clear_vram", {})
            await self.append_to_chat(result, classes="msg-sys")

        # 👇 PASTE STEP 2 HERE 👇
        elif cmd == "/voice":
            if len(parts) > 1 and parts[1].lower() == "disable":
                if getattr(self, 'whisper_model', None) is not None:
                    # Nuke it from memory
                    del self.whisper_model
                    self.whisper_model = None
                    # Force Python to instantly free the RAM
                    import gc; gc.collect()
                    await self.append_to_chat("🔇 Voice module UNLOADED. Memory freed.", classes="msg-sys")
                else:
                    await self.append_to_chat("🔇 Voice module is already disabled.", classes="msg-sys")
            
            elif len(parts) > 1 and parts[1].lower() == "enable":
                if not getattr(self, 'whisper_model', None):
                    loading_msg = await self.append_to_chat("⏳ Loading Voice module into memory...", classes="msg-sys")
                    
                    # Load in background thread so Koko's UI doesn't freeze
                    def load_voice():
                        from faster_whisper import WhisperModel
                        return WhisperModel("tiny.en", device="auto", compute_type="default")
                    
                    loop = asyncio.get_running_loop()
                    self.whisper_model = await loop.run_in_executor(None, load_voice)
                    
                    await loading_msg.remove()
                    await self.append_to_chat("🎙️ Voice module ENABLED. Press F6 to use.", classes="msg-sys")
                else:
                    await self.append_to_chat("🎙️ Voice module is already active.", classes="msg-sys")
            else:
                await self.append_to_chat("❌ Invalid syntax. Use '/voice disable' or '/voice enable'.", classes="msg-error")
        # 👆 PASTE STEP 2 HERE 👆

        elif cmd == "/mcp":
            if len(parts) < 2:
                await self.append_to_chat("Usage: /mcp [add|remove|list] [url]", classes="msg-error")
            else:
                action = parts[1].lower()
                if action == "list":
                    server_tools = {url: [] for url in self.mcp.servers}
                    for tool in self.mcp.available_tools:
                        name = tool["function"]["name"]
                        desc = tool["function"].get("description", "No description")
                        url = self.mcp.tool_directory.get(name)
                        if url in server_tools:
                            server_tools[url].append(f"  └─ [#58a6ff]{name}[/]: [dim]{desc}[/]")
                    
                    mcp_lines = ["[bold white]Active MCP Servers & Tools:[/bold white]"]
                    for url, tools in server_tools.items():
                        mcp_lines.append(f"\n• [#3fb950]{url}[/]")
                        if tools: mcp_lines.extend(tools)
                        else: mcp_lines.append("  └─ [dim italic]Offline or no tools available[/]")
                    await self.append_to_chat(Text.from_markup("\n".join(mcp_lines)), classes="msg-sys")
                    
                elif action == "add" and len(parts) >= 3:
                    self.mcp.servers.append(parts[2])
                    self.settings["mcp_servers"] = self.mcp.servers
                    with open("settings.json", "w", encoding="utf-8") as f: json.dump(self.settings, f, indent=4)
                    await self.action_refresh_mcp()
                    await self.append_to_chat(f"Added & Saved MCP Server.", classes="msg-sys")
                elif action == "remove" and len(parts) >= 3:
                    url = parts[2]
                    if url in self.mcp.servers:
                        self.mcp.servers.remove(url)
                        self.settings["mcp_servers"] = self.mcp.servers
                        with open("settings.json", "w", encoding="utf-8") as f: json.dump(self.settings, f, indent=4)
                        await self.action_refresh_mcp()
                        await self.append_to_chat(f"Removed MCP Server.", classes="msg-sys")
                    else: await self.append_to_chat(f"Server not found.", classes="msg-error")
                else: await self.append_to_chat("Invalid /mcp syntax.", classes="msg-error")
        else: await self.append_to_chat(f"Unknown command: {cmd}", classes="msg-error")

    async def on_chat_text_area_submitted(self, event: ChatTextArea.Submitted) -> None:
        user_text = event.text.strip()
        if not user_text or self.is_processing: return
        try:
            self.query_one("#koko_input").text = ""
            self.query_one("#koko_input").cursor_location = (0, 0)
        except:
            try: self.query_one("#koko_input").load_text("")
            except: pass
            
        timestamp = datetime.now().strftime("%I:%M %p")
        if user_text.startswith("/"):
            asyncio.create_task(self.process_command(user_text, timestamp))
            return
            
        self.write_daily_log(f"USER: {user_text}")
        await self.append_to_chat(f"user@kokocode:~$ {user_text}", classes="msg-user")
        self.chat_history.append({"role": "user", "content": user_text})
        asyncio.create_task(self.process_ai(timestamp, is_background=False))

    async def _tts_worker_loop(self, queue):
        while True:
            item = await queue.get()
            if item is None: break
            text, chat_id = item
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    res = await client.post("http://127.0.0.1:5050/tts", json={"text": text, "voice": "af_bella"})
                    if res.status_code == 200:
                        tg_url = f"https://api.telegram.org/bot{self.tg_token}/sendAudio"
                        files = {"audio": ("voice_note.wav", res.content, "audio/wav")}
                        await client.post(tg_url, data={"chat_id": chat_id}, files=files)
            except Exception as e: self.write_daily_log(f"TTS Error: {e}")
            queue.task_done()

    async def process_ai(self, timestamp, is_background=False, remote_context=None):
        self.is_processing = True
        log_scroll = self.query_one("#chat_log")
        
        # 1. Engine Selection
        current_client = self.gemini_client if self.active_engine == "gemini" else self.local_client
        current_model = self.gemini_model if self.active_engine == "gemini" else self.model_name
        
        if self.active_engine == "gemini" and not self.gemini_key:
            await self.append_to_chat("❌ Gemini API Key not set. Falling back to local.", classes="msg-error")
            current_client = self.local_client
            current_model = self.model_name

        # 2. 🕒 Dynamic Clock Injection
        live_time = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
        sys_prompt = self.chat_history[0]["content"]
        if "[LIVE SYSTEM CLOCK]" in sys_prompt:
            sys_prompt = sys_prompt.split("[LIVE SYSTEM CLOCK]")[0].strip()
        self.chat_history[0]["content"] = f"{sys_prompt}\n\n[LIVE SYSTEM CLOCK]: The exact current local date and time is {live_time}."
        
        # 3. Safe Context Management
        if len(self.chat_history) > 15:
            new_history = [self.chat_history[0]]
            safe_start = len(self.chat_history) - 10
            
            # Step backward until we find a clean 'user' turn to safely cut the history
            while safe_start > 1:
                if self.chat_history[safe_start].get("role") == "user":
                    break
                safe_start -= 1
                
            new_history.extend(self.chat_history[safe_start:])
            self.chat_history = new_history
            
        try:
            while True:
                start_time = time.time()
                
                # 🚀 THE SDK STRIPPING BYPASS
                request_kwargs = {
                    "model": current_model, 
                    "messages": self.chat_history, 
                    "tools": self.native_tools + self.mcp.available_tools if self.native_tools + self.mcp.available_tools else None, 
                    "stream": True, 
                    "stream_options": {"include_usage": True}
                }
                
                if self.active_engine == "gemini":
                    request_kwargs["extra_body"] = {"messages": self.chat_history}
                
                response = await current_client.chat.completions.create(**request_kwargs)
                
                content = ""
                tool_calls_dict = {}
                final_usage = None
                
                cls = "msg-remote" if remote_context else "msg-koko"
                stream_widget = await self.append_to_chat("koko> ...", classes=cls) if not is_background or remote_context else None
                
                thought_widget = None
                tts_queue = asyncio.Queue()
                worker_task = None
                if remote_context and remote_context.get("platform") == "telegram":
                    worker_task = asyncio.create_task(self._tts_worker_loop(tts_queue))
                    
                tts_mode = False
                last_spoken_idx = 0

                async for chunk in response:
                    if getattr(self, "abort_flag", False):
                        if stream_widget: stream_widget.update(Text("🛑 OPERATION ABORTED.", style="#da3633 bold"))
                        self.abort_flag = False
                        self.is_processing = False
                        return
                    
                    if hasattr(chunk, 'usage') and chunk.usage: final_usage = chunk.usage
                    if not chunk.choices: continue
                    delta = chunk.choices[0].delta

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            tool_calls_dict.setdefault(tc.index, {"id": tc.id, "name": "", "arguments": "", "widget": None})
                            if tc.function.name:
                                tool_calls_dict[tc.index]["name"] += tc.function.name
                                name = tool_calls_dict[tc.index]["name"]
                                if name in ["write_local_file", "edit_local_file"]:
                                    tool_calls_dict[tc.index]["widget"] = await self.append_to_chat(f"koko [{name}]> ...", classes="msg-sys")
                            if tc.function.arguments:
                                tool_calls_dict[tc.index]["arguments"] += tc.function.arguments
                                widget = tool_calls_dict[tc.index]["widget"]
                                if widget:
                                    name = tool_calls_dict[tc.index]["name"]
                                    raw_str = tool_calls_dict[tc.index]["arguments"]
                                    display_text = raw_str
                                    if '"content":' in display_text: display_text = display_text.split('"content":', 1)[-1].strip()
                                    elif '"replace_string":' in display_text: display_text = display_text.split('"replace_string":', 1)[-1].strip()
                                    if display_text.startswith('"'): display_text = display_text[1:]
                                    display_text = display_text.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
                                    prefix = Text(f"koko [{name}]> ", style="#58a6ff bold")
                                    md = Markdown(f"```python\n{display_text} ▌\n```")
                                    widget.update(Group(prefix, md))
                                    if log_scroll.scroll_y >= (log_scroll.max_scroll_y - 3): log_scroll.scroll_end(animate=False)
                                
                    if delta.content:
                        content += delta.content
                        if content.startswith("<VOICE>") and not tts_mode: tts_mode = True
                        if tts_mode and worker_task:
                            clean_content = content.replace("<VOICE>", "")
                            unspoken = clean_content[last_spoken_idx:]
                            while True:
                                found_boundary = False
                                for punct in ['. ', '! ', '? ', '\n']:
                                    if punct in unspoken:
                                        split_idx = unspoken.find(punct) + len(punct)
                                        sentence = unspoken[:split_idx].strip()
                                        if len(sentence) > 2: tts_queue.put_nowait((sentence, remote_context["chat_id"]))
                                        last_spoken_idx += split_idx
                                        unspoken = unspoken[split_idx:]
                                        found_boundary = True
                                        break
                                if not found_boundary: break
                        
                        text_to_display = delta.content
                        should_scroll = log_scroll.scroll_y >= (log_scroll.max_scroll_y - 3)
                        
                        if "<think>" in text_to_display:
                            text_to_display = text_to_display.replace("<think>", "").strip()
                            if not thought_widget and (not is_background or remote_context):
                                thought_widget = await self.append_to_chat(f"thought> Thinking...", classes="msg-thought")
                            if thought_widget and text_to_display:
                                thought_widget.update(Text.from_markup(emoji.emojize(f"thought> {text_to_display}", language='alias')))
                                if should_scroll: log_scroll.scroll_end(animate=False)
                        elif "</think>" in text_to_display:
                            text_to_display = text_to_display.split("</think>")[-1].strip()
                            if text_to_display and stream_widget:
                                prefix = Text("koko> ", style="#c9d1d9 bold")
                                md = Markdown(emoji.emojize(text_to_display + " ▌", language='alias'))
                                stream_widget.update(Group(prefix, md))
                                if should_scroll: log_scroll.scroll_end(animate=False)
                        elif stream_widget and not thought_widget:
                            clean_content = content
                            if "</think>" in clean_content: clean_content = clean_content.split("</think>")[-1].strip()
                            clean_content = clean_content.replace("<VOICE>", "").strip()
                            prefix = Text("koko> ", style="#c9d1d9 bold")
                            md = Markdown(emoji.emojize(clean_content + " ▌", language='alias'))
                            stream_widget.update(Group(prefix, md))
                            if should_scroll: log_scroll.scroll_end(animate=False)

                # TTS Cleanup
                if tts_mode and worker_task:
                    unspoken = content.replace("<VOICE>", "")[last_spoken_idx:].strip()
                    if len(unspoken) > 1: tts_queue.put_nowait((unspoken, remote_context["chat_id"]))
                    tts_queue.put_nowait(None)
                elif worker_task: tts_queue.put_nowait(None) 

                # Assemble Tool Calls Payload
                tool_calls_payload = []
                for idx, v in tool_calls_dict.items():
                    call_obj = {
                        "id": v["id"], 
                        "type": "function", 
                        "function": {"name": v["name"], "arguments": v["arguments"]}
                    }
                    if self.active_engine == "gemini":
                        # 🚀 THE REAL FIX: Using the exact key Google demands
                        call_obj["thought_signature"] = "skip_thought_signature_validator"
                    tool_calls_payload.append(call_obj)

                ai_msg = {"role": "assistant", "content": content or None}
                if tool_calls_payload: ai_msg["tool_calls"] = tool_calls_payload
                self.chat_history.append(ai_msg)

                # Tool Execution
                if tool_calls_payload:
                    for tool in tool_calls_payload:
                        matching_tc = next((v for v in tool_calls_dict.values() if v["id"] == tool["id"]), None)
                        if matching_tc and matching_tc.get("widget"):
                            try:
                                args_dict = json.loads(tool["function"]["arguments"])
                                final_code = args_dict.get("content", args_dict.get("replace_string", tool["function"]["arguments"]))
                                prefix = Text(f"koko [{tool['function']['name']}]> ", style="#58a6ff bold")
                                md = Markdown(f"```\n{final_code}\n```")
                                matching_tc["widget"].update(Group(prefix, md))
                            except Exception: pass
                        else:
                            await self.append_to_chat(f" > Terminal Exec: {tool['function']['name']}", classes="msg-tool")
                        
                        tool_result = await self.execute_tool(tool["function"]["name"], json.loads(tool["function"]["arguments"]))
                        self.chat_history.append({
                            "role": "tool", 
                            "tool_call_id": tool["id"], 
                            "name": tool["function"]["name"], 
                            "content": str(tool_result)
                        })
                    continue 
                else:
                    # Finalize Telemetry / UI
                    end_time = time.time()
                    tokens = final_usage.completion_tokens if final_usage else len(content) // 4
                    metrics = self.get_metrics_bar(tokens, start_time, end_time)
                    final_text = content.split("</think>")[-1].strip() if "</think>" in content else content
                    final_text = final_text.replace("<VOICE>", "").strip()
                    
                    if remote_context and remote_context.get("platform") == "telegram":
                        try:
                            import re
                            poster_match = re.search(r'(http://192\.168\.1\.83:8899/Items/[a-zA-Z0-9]+/Images/Primary)', final_text)
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                if poster_match:
                                    poster_url = poster_match.group(1)
                                    local_image_path = os.path.join("downloads", f"temp_poster_{int(time.time())}.jpg")
                                    try:
                                        img_res = await client.get(poster_url)
                                        with open(local_image_path, 'wb') as f: f.write(img_res.content)
                                        with open(local_image_path, 'rb') as photo_file:
                                            files = {"photo": ("poster.jpg", photo_file, "image/jpeg")}
                                            data = {"chat_id": remote_context["chat_id"], "caption": emoji.emojize(final_text, language='alias')}
                                            await client.post(f"https://api.telegram.org/bot{self.tg_token}/sendPhoto", data=data, files=files)
                                        os.remove(local_image_path)
                                    except Exception as e:
                                        await client.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", json={"chat_id": remote_context["chat_id"], "text": emoji.emojize(final_text, language='alias')})
                                else:
                                    await client.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", json={"chat_id": remote_context["chat_id"], "text": emoji.emojize(final_text, language='alias')})
                        except: pass
                    
                    if stream_widget: 
                        should_scroll = log_scroll.scroll_y >= (log_scroll.max_scroll_y - 3)
                        prefix = Text("koko> ", style="#c9d1d9 bold")
                        md = Markdown(emoji.emojize(final_text, language='alias'))
                        metrics_text = Text.from_markup(metrics)
                        stream_widget.update(Group(prefix, md, metrics_text))
                        if thought_widget:
                            final_thoughts = content.split("<think>")[-1].split("</think>")[0].strip()
                            thought_widget.update(Text.from_markup(emoji.emojize(f"thought> {final_thoughts}", language='alias')))
                        if should_scroll: log_scroll.scroll_end(animate=False)
                    elif is_background and not remote_context:
                        if "heartbeat" in content.strip().lower() and len(content) < 15: break 
                        self.write_daily_log(f"KOKO: {content}")
                        prefix = Text("koko [BG]> ", style="#8b949e bold")
                        md = Markdown(emoji.emojize(final_text, language='alias'))
                        metrics_text = Text.from_markup(metrics)
                        await self.append_to_chat(Group(prefix, md, metrics_text), classes="msg-sys")
                    break
        except Exception as e:
            self.write_daily_log(f"AI SYSTEM ERROR: {str(e)}")
            await self.append_to_chat(f" > System Exception: {str(e)}", classes="msg-error")
        finally:
            self.save_context_cache()
            self.is_processing = False

if __name__ == "__main__":
    
    # 👇 PASTE ZOMBIE KILLER HERE 👇
    import sys
    if sys.platform == "win32":
        import ctypes
        import os
        
        def console_ctrl_handler(ctrl_type):
            # This triggers the exact millisecond the red 'X' is clicked
            # os._exit(0) forcefully bypasses all background locks and kills the hardware stream instantly
            os._exit(0)
            return True
            
        # We must store the handler in a variable so Python doesn't garbage collect it
        _win_handler = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(console_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_win_handler, True)
    # 👆 PASTE ZOMBIE KILLER HERE 👆

    app = KokoAgentApp()
    app.run()
    os._exit(0)