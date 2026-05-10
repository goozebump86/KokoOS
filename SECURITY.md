# 🔒 Security Policy — Koko OS

## Overview

Koko OS is a local-first autonomous AI operating system that orchestrates LLMs, MCP servers, and system integrations. This document outlines the security architecture, threat model, and best practices for running Koko OS safely.

---

## 🏗️ Security Architecture

### Local-First Design

Koko OS is designed to run entirely on local hardware. All AI inference, vector storage, and tool execution happens locally by default. Only cloud APIs (Google Gemini, Telegram) require external connections.

### Network Isolation

All MCP servers bind to `127.0.0.1` (localhost only) by default. They are **not** exposed to the network:

```python
uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT)  # ✅ Localhost only
uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)     # ❌ Exposes to entire network
```

**Note:** The current codebase uses `0.0.0.0` for convenience during development. For production, change all servers to `127.0.0.1`.

### Credential Management

| Component | Method | Storage Location |
|-----------|--------|-----------------|
| API Keys | `.env` file | Local filesystem (gitignored) |
| OAuth Tokens | JSON files | Local filesystem (gitignored) |
| Telegram Token | `.env` file | Local filesystem (gitignored) |
| Settings | `settings.json` | Local filesystem (non-sensitive only) |

---

## 🚨 Threat Model

### What We Protect Against

1. **Credential Leakage** — API keys, tokens, and secrets must never appear in source code or be committed to version control
2. **Unauthorized Access** — MCP servers should only accept connections from localhost
3. **Supply Chain Attacks** — Dependencies are pinned in `requirements.txt` for reproducible builds
4. **Data Exfiltration** — Local data (memory, vision logs, emails) stays on the local machine

### What We Don't Protect Against (Out of Scope)

- Physical theft of the machine (use disk encryption like BitLocker)
- Compromised host system (ensure OS and drivers are updated)
- Cloud API provider breaches (Google, Telegram — out of Koko's control)
- Social engineering attacks against the user

---

## 📋 Security Best Practices

### For Users

#### Credential Protection

```bash
# ✅ DO: Use .env file for secrets
GEMINI_API_KEY=your_actual_key_here
TELEGRAM_BOT_TOKEN=your_actual_token_here

# ❌ NEVER do any of these:
echo "MY_KEY=abc123" >> settings.json          # Hardcoding in config
print(f"My key is {API_KEY}")                   # Logging secrets
git add .env                                     # Committing secrets
```

#### Network Security

- Keep all MCP servers on localhost (`127.0.0.1`)
- Use a firewall to block inbound connections to ports 3000–3100
- Never expose Koko OS ports to the internet
- Use HTTPS for any remote Telegram bot proxy (if used)

#### System Hygiene

- Keep Python updated to the latest patch version
- Run `pip list --outdated` monthly and update dependencies
- Regenerate API keys if you suspect exposure
- Use `.gitignore` — verify before every commit: `git status`

### For Developers

#### Code Security Rules

1. **Never hardcode secrets** — Always use environment variables or config.py
2. **Validate all inputs** — Sanitize user input before processing
3. **Use parameterized queries** — Never concatenate strings into SQL (if used)
4. **Set timeouts on all HTTP calls** — Prevent hanging connections:
   ```python
   async with httpx.AsyncClient(timeout=30.0) as client:  # ✅ Has timeout
       response = await client.get(url)
   ```
5. **Use try/except blocks** — Never let exceptions crash the server
6. **Log errors without sensitive data** — Never log API keys or tokens

#### Dependency Security

- Pin dependency versions in `requirements.txt`
- Run `pip-audit` regularly to check for known vulnerabilities:
  ```bash
  pip install pip-audit
  pip-audit
  ```
- Review new dependencies before adding them

#### MCP Server Security

Every new MCP server must:
- Bind to `127.0.0.1` (not `0.0.0.0`)
- Include input validation on all parameters
- Set timeouts on all external calls
- Handle errors gracefully without stack trace leaks
- Not execute arbitrary code from user input

---

## 🔐 File Permissions

### Critical Files (Restricted Access)

| File | Purpose | Permissions |
|------|---------|-------------|
| `.env` | API keys and secrets | Read/Write owner only |
| `client_secrets.json` | Google OAuth credentials | Read/Write owner only |
| `*_token.json` | OAuth tokens | Read/Write owner only |
| `settings.json` | Non-sensitive config | Read/Write owner |

### Git Safety Checklist

Before every commit, verify:

```bash
# Check for accidentally staged secret files
git ls-files | grep -E '\.env|secret|token|credential'

# Verify .gitignore is working
git check-ignore -v .env

# Review all staged files
git diff --cached --name-only
```

---

## 🛡️ Incident Response

### If You Suspect a Credential Leak

1. **Immediately revoke and rotate** the compromised credential:
   - **Gemini API Key**: Go to [Google AI Studio](https://aistudio.google.com/apikey) → Regenerate
   - **Telegram Bot Token**: Message @BotFather → `/revoke`
   - **Gmail OAuth**: Revoke access in [Google Account Security Settings](https://myaccount.google.com/permissions)
   - **YouTube OAuth**: Revoke access in [Google Account Security Settings](https://myaccount.google.com/permissions)

2. **Update the local `.env` file** with new credentials

3. **Check git history** for exposed secrets:
   ```bash
   git log -p --all -S "your_secret_pattern"
   ```

4. **Use git-secrets or truffleHog** to scan for accidental commits:
   ```bash
   # Install truffleHog
   pip install trufflehog
   
   # Scan repository
   trufflehog git file://.
   ```

5. **If secrets were committed to the repo**, consider using [git-filter-repo](https://github.com/newren/git-filter-repo) to remove them from history:
   ```bash
   git filter-repo --replace-text secrets.txt
   ```

### If a Server Is Compromised

1. **Kill the process immediately**:
   ```bash
   # Windows
   taskkill /F /PID <PID>
   
   # Linux/macOS
   kill -9 <PID>
   ```

2. **Free the port**:
   ```bash
   netstat -ano | findstr :<PORT>
   ```

3. **Audit logs** for unauthorized access attempts

4. **Review and update** security settings before restarting

---

## 🔍 Security Audits

### Regular Maintenance Schedule

| Frequency | Task | Command/Method |
|-----------|------|----------------|
| Weekly | Check for git secret leaks | `git status` before commits |
| Monthly | Update dependencies | `pip list --outdated` |
| Monthly | Scan for known vulnerabilities | `pip-audit` |
| Quarterly | Rotate API keys (if recommended) | Via provider dashboards |
| Annually | Full security review | Manual audit of all files |

### Automated Security Scanning

Consider adding these to your CI/CD pipeline:

```bash
# 1. Check for hardcoded secrets
pip install gitleaks
gitleaks detect --source .

# 2. Audit Python dependencies
pip install pip-audit
pip-audit

# 3. Check for exposed credentials in codebase
pip install detect-secrets
detect-secrets scan > baseline.regular
```

---

## 📜 Compliance Notes

Koko OS is designed for personal/local use and does not handle:

- **PII (Personally Identifiable Information)** — No user data collection
- **Financial data** — No payment processing
- **Health information** — No medical data handling
- **Government/classified data** — Not certified for classified environments

If you plan to use Koko OS in a regulated environment, conduct your own security assessment and consult with your organization's security team.

---

## 📞 Reporting Vulnerabilities

If you discover a security vulnerability in Koko OS:

1. **Do NOT open a public GitHub Issue**
2. **Email the maintainer directly** or message via Telegram
3. **Include**: Description, reproduction steps, severity assessment
4. **Allow reasonable time** for a fix before public disclosure

We aim to acknowledge reports within 48 hours and provide updates as fixes are developed.

---

## 📚 Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/) — Web application security risks
- [Python Security Checklist](https://docs.python.org/3/howto/logging.html) — Python best practices
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) — Framework-specific security
- [Model Context Protocol Security](https://modelcontextprotocol.io/docs/concepts/transports) — MCP transport security

---

<div align="center">

**Last Updated:** May 10, 2026  
**Version:** 1.0.0  
**Maintained by:** Koko OS Team

</div>
