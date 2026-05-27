import httpx
import json

memories = [
    {"concept": "Cron Job Scheduling", "details": "Automated morning reports require reliable cron execution; jobs must be rescheduled at end-of-shift for the next day."},
    {"concept": "Telegram Integration Tool", "details": "All responses to Telegram inputs must explicitly use the designated send_telegram_message tool as mandated by system prompt."},
    {"concept": "Diagnostic-First Workflow", "details": "Never execute fixes automatically; always analyze and report the root cause first before applying changes."},
    {"concept": "File System Organization", "details": "Active project files are located in C:\\Users\\gooze\\Downloads, not in subdirectories or backup folders."},
    {"concept": "Script Execution Policy", "details": "Do not run hermes.py directly as the harness is already utilizing it; only read/inspect the file for diagnostics."},
    {"concept": "Context Memory Rule", "details": "System must persistently remember to route Telegram responses back to Telegram when the input originates from that channel."}
]

print(f"Attempting to store {len(memories)} memories into ChromaDB via MemoryMCP...")

with httpx.Client(timeout=30.0) as client:
    stored = 0
    failed = 0
    
    for i, mem in enumerate(memories):
        payload = {
            "jsonrpc": "2.0",
            "id": i + 1,
            "method": "tools/call",
            "params": {
                "name": "store_memory",
                "arguments": mem
            }
        }
        
        try:
            res = client.post('http://127.0.0.1:3021/messages', json=payload)
            
            if res.status_code == 200:
                data = res.json()
                if "result" in data:
                    stored += 1
                    print(f"[OK] Stored: {mem['concept']}")
                else:
                    failed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
    
    print(f"\nREM Sleep Memory Extraction Complete:")
    print(f"  Stored: {stored}/{len(memories)}")
    print(f"  Failed: {failed}/{len(memories)}")
