#!/usr/bin/env python3
"""
Integration test script — validates all external connections before demo.
Run: python scripts/test-integrations.py
"""

import os
import json
import sys
from pathlib import Path

# Load .env if present
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
BOLD  = "\033[1m"
NC    = "\033[0m"

results = []


def check(name: str, ok: bool, detail: str = ""):
    status = f"{GREEN}✅ PASS{NC}" if ok else f"{RED}❌ FAIL{NC}"
    print(f"  {status}  {name}")
    if detail:
        print(f"         {detail}")
    results.append((name, ok))


print(f"\n{BOLD}{'═'*55}{NC}")
print(f"{BOLD}  AI Incident Orchestrator — Integration Check{NC}")
print(f"{BOLD}{'═'*55}{NC}\n")


# ── 1. Incident Service ────────────────────────────────────────
print(f"{BOLD}1. Incident Service{NC}")
try:
    import urllib.request
    url = os.getenv("INCIDENT_SERVICE_URL", "http://localhost:8000")
    with urllib.request.urlopen(f"{url}/", timeout=5) as r:
        data = json.loads(r.read())
    check("Service reachable", True, f"Service: {data.get('service')}")
    with urllib.request.urlopen(f"{url}/metrics", timeout=5) as r:
        m = json.loads(r.read())
    check("Metrics endpoint", True, f"error_rate={m.get('error_rate_pct')}%")
    with urllib.request.urlopen(f"{url}/logs?limit=5", timeout=5) as r:
        l = json.loads(r.read())
    check("Logs endpoint", True, f"total={l.get('total')}")
except Exception as e:
    check("Service reachable", False, str(e))
    check("Metrics endpoint", False, "Service not running")
    check("Logs endpoint", False, "Service not running")

print()


# ── 2. OpenAI API ──────────────────────────────────────────────
print(f"{BOLD}2. OpenAI API{NC}")
api_key = os.getenv("OPENAI_API_KEY", "")
if not api_key or api_key.startswith("sk-proj-your"):
    check("API key configured", False, "Set OPENAI_API_KEY in .env")
    check("API connectivity", False, "No API key")
else:
    check("API key configured", True, f"Key: {api_key[:12]}...{api_key[-4:]}")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        reply = resp.choices[0].message.content.strip()
        check("API connectivity", "OK" in reply or len(reply) < 20, f"Response: {reply}")
    except ImportError:
        check("API connectivity", False, "Run: pip install openai")
    except Exception as e:
        check("API connectivity", False, str(e)[:80])

print()


# ── 3. Slack Webhook ───────────────────────────────────────────
print(f"{BOLD}3. Slack Webhook{NC}")
slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
if not slack_url or "YOUR/WEBHOOK" in slack_url:
    check("Webhook configured", False, "Set SLACK_WEBHOOK_URL in .env")
    check("Webhook reachable", False, "No webhook URL")
else:
    check("Webhook configured", True, f"URL: {slack_url[:50]}...")
    try:
        import urllib.request, urllib.parse
        req = urllib.request.Request(
            slack_url,
            data=json.dumps({"text": "🧪 AI Incident Orchestrator — integration test ping"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            check("Webhook reachable", r.status == 200, f"HTTP {r.status}")
    except Exception as e:
        check("Webhook reachable", False, str(e)[:80])

print()


# ── 4. GitHub API ──────────────────────────────────────────────
print(f"{BOLD}4. GitHub API{NC}")
gh_token = os.getenv("GITHUB_TOKEN", "")
gh_repo  = os.getenv("GITHUB_REPO", "")
if not gh_token or gh_token == "ghp_your_github_token_here":
    check("Token configured", False, "Set GITHUB_TOKEN in .env")
    check("Repo accessible", False, "No token")
elif not gh_repo or "/" not in gh_repo:
    check("Token configured", True)
    check("Repo configured", False, "Set GITHUB_REPO=owner/repo in .env")
else:
    check("Token configured", True, f"Token: {gh_token[:8]}...{gh_token[-4:]}")
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.github.com/repos/{gh_repo}",
            headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        check("Repo accessible", True, f"Repo: {data.get('full_name')} ({data.get('visibility')})")
    except Exception as e:
        check("Repo accessible", False, str(e)[:80])

print()


# ── 5. Kestra ─────────────────────────────────────────────────
print(f"{BOLD}5. Kestra Orchestration Engine{NC}")
try:
    import urllib.request
    kestra_url = os.getenv("KESTRA_URL", "http://localhost:8080")
    with urllib.request.urlopen(f"{kestra_url}/api/v1/flows/search", timeout=5) as r:
        check("Kestra reachable", True, f"URL: {kestra_url}")
    with urllib.request.urlopen(f"{kestra_url}/api/v1/flows/search?namespace=ai.incident.response", timeout=5) as r:
        data = json.loads(r.read())
        flow_count = data.get("total", 0)
    check("Flows loaded", flow_count >= 3, f"{flow_count} flows in ai.incident.response namespace")
except Exception as e:
    check("Kestra reachable", False, str(e)[:80])
    check("Flows loaded", False, "Kestra not running")

print()


# ── Summary ───────────────────────────────────────────────────
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed

print(f"{BOLD}{'═'*55}{NC}")
print(f"{BOLD}  Results: {passed}/{total} checks passed{NC}")
if failed == 0:
    print(f"  {GREEN}{BOLD}🎉 ALL CHECKS PASSED — Ready to demo!{NC}")
else:
    print(f"  {YELLOW}⚠️  {failed} check(s) failed — see above for details{NC}")
    print(f"\n  {BOLD}Quick fixes:{NC}")
    print(f"  • Services not running? → docker compose up -d")
    print(f"  • Missing API keys?    → cp .env.example .env && edit .env")
    print(f"  • Flows not loaded?    → docker compose restart flow-loader")
print(f"{BOLD}{'═'*55}{NC}\n")

sys.exit(0 if failed == 0 else 1)
