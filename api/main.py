import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "companies.json"
KEYS_FILE = BASE_DIR / "data" / "api_keys.json"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
RATE_WINDOWS: dict[str, list[float]] = defaultdict(list)

TIER_LIMITS = {
    "free": {"rpm": 30, "credits": 100},
    "starter": {"rpm": 120, "credits": 1000},
    "growth": {"rpm": 600, "credits": 10000},
}

DEFAULT_DEMO_KEY = "demo_key_12345"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


@lru_cache(maxsize=1)
def load_companies() -> tuple[dict, ...]:
    data = read_json(DATA_FILE, [])
    if not isinstance(data, list):
        return ()
    return tuple(company for company in data if isinstance(company, dict))


@lru_cache(maxsize=1)
def company_index() -> dict[int, dict]:
    index = {}
    for company in load_companies():
        try:
            index[int(company.get("id"))] = company
        except (TypeError, ValueError):
            continue
    return index


@lru_cache(maxsize=1)
def searchable_companies() -> tuple[tuple[dict, str], ...]:
    fields = ("name", "tagline", "description", "industry", "subindustry", "location", "batch", "status")
    searchable = []
    for company in load_companies():
        values = [normalize_text(company.get(field)) for field in fields]
        values.extend(normalize_text(tag) for tag in string_list(company.get("tags")))
        values.extend(normalize_text(tag) for tag in string_list(company.get("tech_stack")))
        searchable.append((company, " ".join(values)))
    return tuple(searchable)


def data_updated_at() -> Optional[str]:
    scraped_times = [normalize_text(company.get("scraped_at")) for company in load_companies() if company.get("scraped_at")]
    if scraped_times:
        return max(scraped_times)
    if not DATA_FILE.exists():
        return None
    return datetime.fromtimestamp(DATA_FILE.stat().st_mtime, timezone.utc).isoformat()


def configured_direct_keys() -> dict[str, dict]:
    keys = {}
    for key in os.getenv("DIRECT_API_KEYS", DEFAULT_DEMO_KEY).split(","):
        clean = key.strip()
        if clean:
            keys[clean] = {"source": "direct", "tier": os.getenv("DEFAULT_TIER", "free")}

    stored = read_json(KEYS_FILE, {})
    if isinstance(stored, dict):
        for key, meta in stored.items():
            if isinstance(meta, dict):
                keys[key] = {**meta, "source": meta.get("source", "direct")}
    return keys


def check_rate_limit(key: str, tier: str) -> None:
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    now = time.time()
    RATE_WINDOWS[key] = [entry for entry in RATE_WINDOWS[key] if now - entry < 60]
    if len(RATE_WINDOWS[key]) >= limits["rpm"]:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    RATE_WINDOWS[key].append(now)


async def get_api_key(request: Request) -> dict:
    rapidapi_key = request.headers.get("X-RapidAPI-Key")
    direct_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    rapidapi_secret = os.getenv("RAPIDAPI_PROXY_SECRET")

    if rapidapi_key:
        if rapidapi_secret:
            supplied_secret = request.headers.get("X-RapidAPI-Proxy-Secret")
            if supplied_secret != rapidapi_secret:
                raise HTTPException(status_code=403, detail="Invalid RapidAPI proxy secret")
        tier = request.headers.get("X-RapidAPI-Subscription", os.getenv("DEFAULT_TIER", "free")).lower()
        check_rate_limit(f"rapidapi:{rapidapi_key}", tier)
        return {"source": "rapidapi", "tier": tier}

    if not direct_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    keys = configured_direct_keys()
    if direct_key not in keys:
        raise HTTPException(status_code=403, detail="Invalid API key")

    meta = keys[direct_key]
    tier = str(meta.get("tier", "free")).lower()
    check_rate_limit(f"direct:{direct_key}", tier)
    return {**meta, "tier": tier}


def paginate(items: list[dict], page: int, limit: int) -> dict:
    start = (page - 1) * limit
    return {
        "total": len(items),
        "page": page,
        "limit": limit,
        "results": items[start : start + limit],
    }


def score_lead(company: dict) -> int:
    score = 0
    if company.get("website"):
        score += 25
    if company.get("team_size"):
        score += min(int(company.get("team_size") or 0), 500) // 20
    if company.get("industry"):
        score += 10
    if company.get("location"):
        score += 10
    if company.get("tech_stack"):
        score += min(len(company.get("tech_stack", [])), 8) * 4
    if normalize_text(company.get("status")) in {"active", "public", "acquired"}:
        score += 20
    return score


def matches_filter(company: dict, field: str, expected: Optional[str]) -> bool:
    if not expected:
        return True
    return normalize_text(expected) in normalize_text(company.get(field))


app = FastAPI(
    title="YC Startup Leads API",
    version="4.0.0",
    description="Fast searchable YC company data for prospecting, enrichment, and market research.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "YC Startup Leads API",
        "version": app.version,
        "docs": "/docs",
        "endpoints": ["/companies", "/company/{id}", "/leads/high-value", "/metadata", "/health"],
    }


@app.get("/companies")
async def companies(
    q: Optional[str] = Query(None, description="Search name, tagline, description, tags, industry, and location."),
    tech: Optional[str] = Query(None, description="Filter by tag or inferred tech/category."),
    industry: Optional[str] = Query(None, description="Filter by YC industry."),
    batch: Optional[str] = Query(None, description="Filter by YC batch, for example Winter 2024."),
    status: Optional[str] = Query(None, description="Filter by status such as Active, Public, or Acquired."),
    location: Optional[str] = Query(None, description="Filter by location."),
    min_team_size: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    auth: dict = Depends(get_api_key),
):
    query = normalize_text(q)
    tech_query = normalize_text(tech)
    results = []

    for company, search_blob in searchable_companies():
        if query and query not in search_blob:
            continue
        tech_values = string_list(company.get("tech_stack")) + string_list(company.get("tags"))
        if tech_query and tech_query not in " ".join(tech_values).lower():
            continue
        if not matches_filter(company, "industry", industry):
            continue
        if not matches_filter(company, "batch", batch):
            continue
        if not matches_filter(company, "status", status):
            continue
        if not matches_filter(company, "location", location):
            continue
        if min_team_size is not None and int(company.get("team_size") or 0) < min_team_size:
            continue
        results.append(company)

    return {**paginate(results, page, limit), "auth_source": auth["source"]}


@app.get("/company/{company_id}")
async def get_company(company_id: int, auth: dict = Depends(get_api_key)):
    company = company_index().get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return {**company, "auth_source": auth["source"]}


@app.get("/leads/high-value")
async def high_value(
    industry: Optional[str] = None,
    location: Optional[str] = None,
    min_team_size: int = Query(1, ge=0),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    auth: dict = Depends(get_api_key),
):
    leads = []
    for company in load_companies():
        if not company.get("name") or not company.get("website"):
            continue
        if int(company.get("team_size") or 0) < min_team_size:
            continue
        if not matches_filter(company, "industry", industry):
            continue
        if not matches_filter(company, "location", location):
            continue
        leads.append({**company, "lead_score": score_lead(company)})

    leads.sort(key=lambda item: item["lead_score"], reverse=True)
    return {"total": len(leads), "limit": limit, "results": leads[:limit], "auth_source": auth["source"]}


@app.get("/metadata")
async def metadata(auth: dict = Depends(get_api_key)):
    companies_data = load_companies()
    return {
        "companies": len(companies_data),
        "industries": sorted({c.get("industry") for c in companies_data if c.get("industry")}),
        "batches": sorted({c.get("batch") for c in companies_data if c.get("batch")}),
        "statuses": sorted({c.get("status") for c in companies_data if c.get("status")}),
        "updated_at": data_updated_at(),
        "auth_source": auth["source"],
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "companies": len(load_companies()),
        "data_updated_at": data_updated_at(),
        "timestamp": utc_now(),
    }


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
