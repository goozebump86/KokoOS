from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re
import os
import fnmatch
import base64

app = FastAPI(title="SecretScan MCP")

class ScanRequest(BaseModel):
    directory: str
    max_depth: int = 3
    ignore_patterns: list = [".git", "__pycache__", "venv", ".env", "node_modules", "*.min.js"]

class ScanResult(BaseModel):
    findings: list
    total_files_scanned: int
    risk_level: str

def get_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    probability = [float(s.count(c)) / len(s) for c in set(s)]
    return -sum(p * (2**p) for p in probability if p > 0)

def is_high_entropy(value: str, min_length: int = 16) -> bool:
    """Check if a value looks like a random secret."""
    if len(value) < min_length:
        return False
    entropy = get_entropy(value)
    return entropy > 3.8

SECRET_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret Key": r"(?<=aws_secret_access_key\s*=\s*)[A-Za-z0-9/+=]{40}",
    "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36,255}",
    "Generic API Key": r"[Aa][Pp][Ii][_]?[Kk][Ee][Yy]\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?",
    "Generic Secret": r"[Ss][Ee][Cc][Rr][Ee][Tt]\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{8,})['\"]?",
    "Database Password": r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?(\S+?)['\"]?(?=\s|$)",
    "Private Key": r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
    "OpenAI API Key": r"sk-proj-[A-Za-z0-9_-]{20,}",
    "Slack Token": r"xox[baprs]-[0-9a-zA-Z-]+",
    "Google API Key": r"AIza[0-9A-Za-z_\-]{35}",
    "Stripe Key": r"(sk|pk)_(test|live)_[A-Za-z0-9]{24,}",
    "JWT Token": r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
    "Heroku API Key": r"[Hh]eroku.*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "DigitalOcean Token": r"dop_v1_[A-Za-z0-9_-]{64}",
}

def scan_file(filepath: str) -> list:
    """Scan a single file for secrets."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        lines = content.split('\n')
        findings = []
        
        for line_num, line in enumerate(lines, 1):
            if len(line) > 500:
                continue
                
            for secret_type, pattern in SECRET_PATTERNS.items():
                if re.search(pattern, line):
                    findings.append({
                        "file": filepath,
                        "line": line_num,
                        "type": secret_type,
                        "match": line.strip()[:100] + ("..." if len(line.strip()) > 100 else "")
                    })
            
            assign_patterns = [
                r"([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*['\"]([A-Za-z0-9]{16,})['\"]",
            ]
            for ap in assign_patterns:
                match = re.search(ap, line)
                if match:
                    var_name = match.group(1).lower()
                    secret_val = match.group(2)
                    secret_keywords = ['key', 'token', 'secret', 'password', 'passwd', 'pwd', 'api_key', 'auth', 'access', 'credential']
                    if any(kw in var_name for kw in secret_keywords):
                        if is_high_entropy(secret_val):
                            finding_type = f"High-entropy {var_name}"
                            already_found = any(f["type"] == finding_type and f["line"] == line_num for f in findings)
                            if not already_found:
                                findings.append({
                                    "file": filepath,
                                    "line": line_num,
                                    "type": finding_type,
                                    "match": line.strip()[:100] + ("..." if len(line.strip()) > 100 else "")
                                })
        
        return findings
        
    except Exception:
        return []

def should_ignore(filepath: str, ignore_patterns: list) -> bool:
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(os.path.basename(filepath), pattern):
            return True
    return False

def get_depth(path: str, base: str) -> int:
    rel = os.path.relpath(path, base)
    if rel == '.':
        return 0
    return rel.count(os.sep) + 1

@app.get("/health")
def health():
    return {"status": "ok", "service": "SecretScan MCP"}

@app.post("/scan", response_model=ScanResult)
def scan_directory(req: ScanRequest):
    if not os.path.isdir(req.directory):
        raise HTTPException(status_code=404, detail=f"Directory not found: {req.directory}")
    
    all_findings = []
    files_scanned = 0
    
    for root, dirs, files in os.walk(req.directory):
        current_depth = get_depth(root, req.directory)
        if current_depth > req.max_depth:
            dirs.clear()
            continue
        
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git', 'venv', '.venv']]
        
        for filename in files:
            filepath = os.path.join(root, filename)
            
            if should_ignore(filepath, req.ignore_patterns):
                continue
                
            files_scanned += 1
            findings = scan_file(filepath)
            all_findings.extend(findings)
    
    high_risk_types = ["Private Key", "AWS Access Key", "GitHub Token", "Stripe Key"]
    has_high_risk = any(f["type"] in high_risk_types for f in all_findings)
    total_severity = len(all_findings)
    
    if has_high_risk or total_severity > 5:
        risk = "CRITICAL"
    elif total_severity > 0:
        risk = "WARNING"
    else:
        risk = "CLEAN"
    
    return ScanResult(
        findings=all_findings,
        total_files_scanned=files_scanned,
        risk_level=risk
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9087)