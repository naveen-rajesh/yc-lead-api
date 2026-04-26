# 🚀 YC Lead API — FULL UPDATED VERSION

import json
import hashlib
import secrets
import time
import subprocess
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

# ── Data ─────────────────────────────────────

DATA_FILE = Path(__file__).parent.parent / "data" / "companies.json"
KEYS_FILE = Path(__file__).parent.parent / "data" / "api_keys.json"

@lru_cache()
def load_companies() -> list[dict]:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def load_keys() -> dict:
    if KEYS_FILE.exists():
        with open(KEYS_FILE) as f:
            return json.load(f)
    default = {
        "demo_key_12345": {
            "name": "Demo User",
            "email": "demo@example.com",
            "tier": "free",
            "credits_used": 0,
            "created_at": datetime.utcnow().isoformat(),
            "calls": [],
        }
    }
    save_keys(default)
    return default


def save_keys(keys: dict):
    KEYS_FILE.parent.mkdir(exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

# ── Rate limiting ─────────────────────────────

RATE_WINDOWS = defaultdict(list)
TIER_LIMITS = {
    "free": {"rpm": 10, "credits": 100},
    "starter": {"rpm": 60, "credits": 1000},
    "growth": {"rpm": 300, "credits": 10000},
}


def check_rate_limit(key, tier):
    rpm = TIER_LIMITS[tier]["rpm"]
    now = time.time()
    RATE_WINDOWS[key] = [t for t in RATE_WINDOWS[key] if now - t < 60]
    if len(RATE_WINDOWS[key]) >= rpm:
        return False
    RATE_WINDOWS[key].append(now)
    return True

# ── App ─────────────────────────────────────

app = FastAPI(title="YC Lead API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ────────────────────────────────────

async def get_api_key(request: Request):
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not key:
        raise HTTPException(401, "Missing API key")

    keys = load_keys()
    if key not in keys:
        raise HTTPException(403, "Invalid API key")

    meta = keys[key]
    tier = meta.get("tier", "free")

    if not check_rate_limit(key, tier):
        raise HTTPException(429, "Rate limit exceeded")

    if meta["credits_used"] >= TIER_LIMITS[tier]["credits"]:
        raise HTTPException(402, "Credits exhausted")

    meta["credits_used"] += 1
    keys[key] = meta
    save_keys(keys)

    print(f"[API CALL] {meta['email']} | tier={tier}")

    return meta

# ── Routes ──────────────────────────────────

@app.get("/")
async def root():
    return {
        "message": "YC Lead API",
        "get_api_key": "/keys/create",
        "usage": "Pass X-API-Key header"
    }

@app.get("/companies")
async def companies(
    q: Optional[str] = None,
    tech: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    auth: dict = Depends(get_api_key)
):
    data = load_companies()

    if q:
        data = [c for c in data if q.lower() in c["name"].lower()]

    if tech:
        data = [c for c in data if tech.lower() in " ".join(c.get("tech_stack", [])).lower()]

    start = (page - 1) * limit
    return {
        "total": len(data),
        "results": data[start:start+limit]
    }

@app.get("/company/{id}")
async def get_company(id: int, auth: dict = Depends(get_api_key)):
    for c in load_companies():
        if c["id"] == id:
            return c
    raise HTTPException(404, "Not found")

# 💰 HIGH VALUE ENDPOINT
@app.get("/leads/high-value")
async def high_value(auth: dict = Depends(get_api_key)):
    data = load_companies()
    leads = [
        c for c in data
        if c.get("website") and c.get("founders") and c.get("tech_stack")
    ]
    return leads[:20]

# 🔁 Trigger scraper remotely
@app.post("/admin/scrape")
async def trigger_scrape():
    subprocess.Popen(["python3", "scraper/yc_scraper.py", "50"])
    load_companies.cache_clear()
    return {"status": "scraping started"}

# 🩺 Health check endpoint
@app.get("/health")
async def health():
    data = load_companies()
    return {
        "status": "ok",
        "companies": len(data),
        "timestamp": datetime.utcnow().isoformat()
    }

# 🔑 Create API key
@app.post("/keys/create")
async def create_key(name: str, email: str):
    raw = f"{email}-{secrets.token_hex(16)}"
    key = hashlib.sha256(raw.encode()).hexdigest()[:32]

    keys = load_keys()
    keys[key] = {
        "name": name,
        "email": email,
        "tier": "free",
        "credits_used": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    save_keys(keys)

    return {"api_key": key}

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
