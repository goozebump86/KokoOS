@echo off
title Koko OS Master Boot Controller
echo ===================================================
echo      KOKO OS MASTER BOOT SEQUENCE INITIATED
echo ===================================================
echo.

echo [1/12] Booting The Brain (Qwen 3.6 on Port 8080)...
start "Koko Brain (8080)" llama-server -m C:\Users\gooze\.cache\huggingface\hub\models--unsloth--Qwen3.6-35B-A3B-GGUF\snapshots\9280dd353ab587157920d5bd391ada414d84e552\Qwen3.6-35B-A3B-UD-Q4_K_M.gguf -fa on --fit on --ctx-size 128000 --no-webui --jinja --no-mmap --port 8080 --host 0.0.0.0 --temperature 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 1.5 --repeat-penalty 1.0 
:: Give the GPUs 3 seconds to allocate VRAM before hammering the CPU with the rest of the servers
timeout /t 5 >nul

echo [2/14] Booting Voice Engine (Port 5050)...
start "Kokoro Voice Engine (5050)" python kokoro_voice_server.py

echo [3/14] Booting Web Scraper (Port 3008)...
start "Koko WebBrowser (3008)" python WebBrowserMCP.py

echo [4/14] Booting Stateful Outlook Email (Port 3015)...
start "Koko Outlook (3015)" python outlookmcp.py

echo [5/14] Booting ComfyUI Image Editor (Port 3017)...
start "Koko ComfyUI Edit (3017)" python ComfyUIEdit.py

echo [6/14] Booting ComfyUI Audio Engine (Port 3018)...
start "Koko ComfyUI Audio (3018)" python ComfyUIAudio.py

echo [7/14] Booting YouTube Content Factory (Port 3019)...
start "Koko YouTube Publisher (3019)" python YoutubePublisherMCP.py

echo [8/14] Booting Senior Dev Tools (Port 3020)...
start "Koko Coder MCP (3020)" python CoderMCP.py

echo [9/14] Booting Infinite Recall Database (Port 3021)...
start "Koko Memory Engine (3021)" python MemoryMCP.py

echo [10/14] Booting Ghost in the Machine (Port 3022)...
start "Koko DeepOS Sysadmin (3022)" python DeepOSMCP.py

echo [11/14] Booting Neural Graph HUD (Port 8090)...
start "Koko Neural HUD (8090)" cmd /k "cd Koko_HUD && python neural_graph_server.py"

echo [12/14] Booting Gmail-Email Server (Port 3035)...
start "Gmail (3022) python GmailMCP.py

echo [13/14] Booting Jellyfin Media Hub (Port 3010)...
start "Koko Jellyfin (3010)" python JellyfinMCP.py

echo [14/14] Booting ComfyUI Image Generation(Z-Image) (port 3011)...
start "ComfUI Image (3011)" python ComfyUIimage.py

echo[15/15] Booting System Monitor (port 3055)...
start "System Monitor" python C:\Users\gooze\Downloads\mcp_servers\sys_monitor.py
echo [15/15] Waking up Koko Core OS Shell...
:: Brief pause to ensure all local ports are established before Hermes connects
timeout /t 2 >nul
start "KOKO OS TERMINAL" python hermes.py

echo.
echo ===================================================
echo ALL SYSTEMS GO. 
echo Neural network is fully awake and self-sustaining.
echo ===================================================
echo.
echo Press any key to close this bootloader window...
pause >nul