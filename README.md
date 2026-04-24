# 🌴 Koko OS - Autonomous Director Agent System

![Koko OS Logo](https://img.shields.io/badge/Koko-OS-v1.0.0-blue) ![Python](https://img.shields.io/badge/Python-3.9+-green.svg) ![License](https://img.shields.io/badge/License-MIT-yellow.svg)

> **Koko OS** is a fully autonomous AI Operating System that acts as a Director Agent, orchestrating local LLMs, cloud AI APIs, MCP (Model Context Protocol) servers, and real-time system integration into a unified intelligence platform.

---

## ✨ Features

| Category | Features |
|----------|----------|
| 🧠 **AI Engine** | Dual-engine architecture (Local Qwen + Google Gemini), hot-swappable models |
| 💻 **MCP Integration** | 12+ Model Context Protocol servers for code, research, media, and more |
| 🔒 **Security** | Environment-based credential management, Git-safe secrets |
| 🎙️ **Voice** | Real-time Whisper transcription with push-to-talk interface |
| 👁️ **Vision** | Passive screen monitoring with chromaDB-powered visual memory |
| 📱 **Remote Control** | Telegram bot integration for remote commands and media delivery |
| 📺 **Media** | ComfyUI image/audio generation, YouTube Shorts upload pipeline |
| 🎬 **Entertainment** | Auto-generated Norah Jones-style music tracks with video thumbnails |
| 📧 **Email** | Gmail and Outlook integration for inbox automation |
| 🗄️ **Media Server** | Jellyfin library search and management |
| ⏰ **Cron System** | Automated task scheduler with heartbeat monitoring |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   KOKO OS SHELL                      │
│                    (hermes.py)                       │
│  ┌──────────┐  ┌────────────┐  ┌────────────────┐   │
│  │ Gemini AI│  │ Local LLM  │  │ Coder LLM      │   │
│  │ (Gemini) │  │ (Qwen-35B) │  │ (GLM-4-Flash)  │   │
│  └──────────┘  └─────┬──────┘  └────────┬───────┘   │
│                      │                  │           │
│              ┌───────▼──────────────────▼───────┐    │
│              │     DIRECTOR AGENT CORE          │    │
│              │  • Chat History Management       │    │
│              │  • Tool Routing & Execution      │    │
│              │  • Context Cache System          │    │
│              │  • Cron & Gateway Scheduler      │    │
│              └──────────────┬───────────────────┘    │
│                             │                        │
│              ┌──────────────▼───────────────────┐    │
│              │       MCP SERVER LAYER           │    │
│              │  CoderMCP • DeepOSMCP • Gmail   │    │
│              │  JellyfinMCP • MemoryMCP • ...   │    │
│              └──────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
         │                   │                    │
    ┌────▼────┐       ┌──────▼──────┐      ┌─────▼─────┐
    │ComfyUI  │       │Telegram Bot │      │  Jellyfin  │
    │Generation│       │Remote Ctrl │      │ Media Server│
    └─────────┘       └─────────────┘      └───────────┘
```

---

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- Git installed and in PATH
- Local LLM serving on `localhost:8080` (Qwen-35B recommended)
- Optional: Coder LLM on `localhost:8081` (GLM-4-Flash)

### 🚀 One-Click Installation (Recommended)

Just double-click the install script and everything sets up automatically:

**Windows:**
```cmd
double-click install.bat
```

**Linux/macOS:**
```bash
chmod +x install.sh && ./install.sh
```

The installer will:
1. ✅ Detect your Python installation
2. ✅ Create an isolated virtual environment (`.venv`)
3. ✅ Install all 20+ dependencies from `requirements.txt`
4. ✅ Download Playwright browsers for web scraping & email automation
5. ✅ Give you step-by-step next instructions

### 🔧 Manual Installation

If you prefer to install manually:

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/KokoOS.git
cd KokoOS

# 2. Create and activate virtual environment
python -m venv .venv
# Windows:     .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

# 3. Configure environment
copy .env.example .env        # Windows
cp .env.example .env          # Linux/macOS

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Install Playwright browsers manually
playwright install chromium
```

---

## 🔧 Configuration

### Environment Variables (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | `AIzaSy...` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | `809103...:AAHHrXxv...` |
| `LOCAL_LLM_BASE` | Local LLM endpoint | `http://localhost:8080/v1` |
| `LOCAL_LLM_MODEL` | Local model name | `qwen-35b-local` |
| `CODER_LLM_BASE` | Coder LLM endpoint | `http://localhost:8081/v1` |
| `CODER_LLM_MODEL` | Coder model name | `glm-4-flash` |

### Active MCP Servers

Koko OS connects to 12+ external Model Context Protocol servers. Each runs as a separate FastAPI process on its own port:

| Server File | Port | Function |
|-------------|------|----------|
| CoderMCP.py | 3020 | AI code generation & management |
| ComfyUIAudio.py | 3018 | Audio/music synthesis via ComfyUI |
| ComfyUIEdit.py | 3017 | Image editing via ComfyUI |
| ComfyUIimage.py | 3011 | Image generation via ComfyUI |
| DeepOSMCP.py | 3022 | System monitoring, process control |
| GmailMCP.py | 3035 | Gmail API (read/send/manage) |
| JellyfinMCP.py | 3010 | Jellyfin media library search |
| MemoryMCP.py | 3021 | Vector memory storage & retrieval |
| outlookmcp.py | 3015 | Outlook/Exchange email automation |
| WebBrowserMCP.py | 3008 | Headless web scraping & searching |
| YoutubePublisherMCP.py | 3019 | YouTube Shorts upload pipeline |

### 🎮 Running KokoOS

**Option 1: Full Boot (All Servers at Once)**
```cmd
# Windows
boot_koko.bat
```

**Option 2: Run Individual Servers**
```bash
python CoderMCP.py             # Port 3020 - AI Code Assistant
python ComfyUIAudio.py         # Port 3018 - Music Generation
python ComfyUIEdit.py          # Port 3017 - Image Editing
python ComfyUIimage.py         # Port 3011 - Image Generation
python DeepOSMCP.py            # Port 3022 - System Monitor & Control
python GmailMCP.py             # Port 3035 - Gmail Integration
python JellyfinMCP.py          # Port 3010 - Media Library Search
python MemoryMCP.py            # Port 3021 - Long-Term Memory
python outlookmcp.py           # Port 3015 - Outlook Email Automation
python WebBrowserMCP.py        # Port 3008 - Web Scraping & Research
python YoutubePublisherMCP.py  # Port 3019 - YouTube Publishing

# Main Shell (connects to all MCP servers above)
python hermes.py               # Interactive Koko OS Terminal
```

**Option 3: Start Just the Shell**
If your MCP servers are already running, just launch the main shell:
```bash
python hermes.py
```

---

## 🎮 Usage

### Interactive Shell Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/models` | List active AI engines |
| `/settings` | Open configuration modal |
| `/passive [on\|off]` | Toggle passive vision monitoring |
| `/flush` | Reset short-term memory cache |
| `/vram` | Clear GPU VRAM |
| `/mcp list\|add\|remove` | Manage MCP servers |
| `/voice enable\|disable` | Load/unload Whisper voice module |

### Keyboard Shortcuts

| Key | Function |
|-----|----------|
| `Ctrl+C` | Power down Koko OS |
| `Ctrl+S` | Open settings modal |
| `F2` | Toggle PLAN/BUILD mode |
| `F3` | Attach image from clipboard |
| `F4` | Switch AI engine (Local ↔ Gemini) |
| `F5` | Refresh MCP tool sync |
| `F8` | Push-to-talk voice input |

---

## 📁 Project Structure

```
KokoOS/
├── hermes.py                 # Main OS shell & director agent
├── config.py                 # Secure credential loader
├── CoderMCP.py               # Senior dev MCP server (Port 3020)
├── DeepOSMCP.py              # Deep system operations MCP
├── GmailMCP.py               # Gmail integration MCP
├── JellyfinMCP.py            # Jellyfin media MCP
├── MemoryMCP.py              # Long-term memory MCP
├── outlookmcp.py             # Outlook email MCP
├── WebBrowserMCP.py          # Web scraping MCP
├── YoutubePublisherMCP.py    # YouTube Shorts publisher MCP
├── ComfyUIAudio.py           # Audio generation utilities
├── ComfyUIEdit.py            # Image editing tools
├── ComfyUIimage.py           # Image generation scripts
├── settings.json             # Non-sensitive configuration
├── boot_koko.bat             # Windows launcher script
├── .env.example              # Environment template
├── requirements.txt          # Python dependencies
├── SECURITY.md               # Security documentation
└── memory/                   # LTM storage & cron database
    ├── MEMORY.md             # Long-term memory
    ├── cron.json             # Cron job database
    ├── heartbeat.md          # System heartbeat
    └── vision_db/            # ChromaDB vision memories
```

---

## 🔒 Security

Koko OS takes security seriously:

- ✅ **Zero hardcoded credentials** - All secrets stored in `.env`
- ✅ **Git-safe** - `.gitignore` blocks all sensitive files
- ✅ **Credential validation** - Startup checks for required keys
- ✅ **Masked output** - Sensitive values hidden in logs
- ✅ **Secure MCP** - Local-only server communication

> ⚠️ **NEVER commit your `.env` file to version control!**

---

## 🎬 Entertainment Pipeline

Koko OS can autonomously generate and publish content:

1. **Music Generation**: Norah Jones-style tracks via ComfyUI
2. **Video Creation**: Vertical cover images + AI-generated visuals
3. **YouTube Upload**: Auto-uploads to YouTube Shorts
4. **Telegram Delivery**: Sends media to configured chat

**Schedule**: Runs every 24 hours automatically via cron system.

---

## 📊 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16 GB+ |
| Storage | 10 GB | 50 GB+ |
| GPU | NVIDIA GTX 1060 | RTX 3070+ (for ComfyUI) |
| CPU | Quad-core | 8-core+ |

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenAI SDK** - LLM API integration
- **FastAPI** - MCP server framework
- **ChromaDB** - Vector database for vision memory
- **Whisper** - Voice transcription (faster-whisper)
- **ComfyUI** - AI image and audio generation
- **Textual** - Terminal UI framework

---

## 📬 Contact

For issues, feature requests, or questions:

- Open an Issue on GitHub
- Telegram: [@YourKokoBot](https://t.me/YourKokoBot)

---

<div align="center">

**Built with ❤️ by [YOUR_NAME]** | *Version 1.0.0* | © 2026 Koko OS

</div>
