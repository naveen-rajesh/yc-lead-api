import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "companies.json"
YC_COMPANIES_URL = "https://www.ycombinator.com/companies"
ALGOLIA_APP_ID = os.getenv("YC_ALGOLIA_APP_ID", "45BWZJ1SGC")
ALGOLIA_INDEX = os.getenv("YC_ALGOLIA_INDEX", "YCCompany_production")
ALGOLIA_API_KEY = os.getenv(
    "YC_ALGOLIA_API_KEY",
    "NzllNTY5MzJiZGM2OTY2ZTQwMDEzOTNhYWZiZGRjODlhYzVkNjBmOGRjNzJiMWM4ZTU0ZDlhYTZjOTJiMjlhMWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_algolia_api_key(client: httpx.AsyncClient) -> str:
    response = await client.get(YC_COMPANIES_URL)
    response.raise_for_status()

    match = re.search(r'window\.AlgoliaOpts = \{"app":"[^"]+","key":"([^"]+)"\}', response.text)
    if match:
        return match.group(1)

    return ALGOLIA_API_KEY


def normalize_company(hit: dict, position: int) -> dict:
    slug = hit.get("slug") or str(hit.get("objectID", ""))
    tags = hit.get("tags") or []
    industries = hit.get("industries") or []

    return {
        "id": int(hit.get("id") or hit.get("objectID") or position),
        "name": hit.get("name") or "",
        "tagline": hit.get("one_liner") or "",
        "description": hit.get("long_description") or "",
        "batch": hit.get("batch") or "",
        "status": hit.get("status") or "",
        "website": hit.get("website") or "",
        "location": hit.get("all_locations") or "",
        "team_size": hit.get("team_size"),
        "industry": hit.get("industry") or "",
        "subindustry": hit.get("subindustry") or "",
        "linkedin": "",
        "twitter": "",
        "founders": [],
        "tags": tags,
        "tech_stack": sorted(set(tags + industries)),
        "yc_url": f"https://www.ycombinator.com/companies/{slug}" if slug else "",
        "email": "",
        "scraped_at": utc_now(),
    }


async def fetch_page(
    client: httpx.AsyncClient,
    api_key: str,
    page: int,
    hits_per_page: int,
) -> dict:
    params = urlencode(
        {
            "hitsPerPage": hits_per_page,
            "page": page,
            "facetFilters": '["yc_public"]',
        }
    )
    response = await client.post(
        f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query",
        headers={
            "x-algolia-application-id": ALGOLIA_APP_ID,
            "x-algolia-api-key": api_key,
        },
        json={"params": params},
    )
    response.raise_for_status()
    return response.json()


async def scrape(limit=50):
    results = []
    page = 0
    hits_per_page = min(max(limit, 1), 100)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        api_key = await get_algolia_api_key(client)

        while len(results) < limit:
            payload = await fetch_page(client, api_key, page, hits_per_page)
            hits = payload.get("hits") or []
            if not hits:
                break

            for hit in hits:
                results.append(normalize_company(hit, len(results) + 1))
                if len(results) >= limit:
                    break

            page += 1
            if page >= int(payload.get("nbPages") or 0):
                break

    return results


async def scrape_and_save(limit=50):
    results = await scrape(limit)
    if not results:
        raise RuntimeError("YC returned no companies; refusing to overwrite data with an empty file")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = OUTPUT_FILE.with_suffix(".json.tmp")
    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    temp_file.replace(OUTPUT_FILE)

    print(f"Saved {len(results)} companies")
    return results


if __name__ == "__main__":
    import sys

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    asyncio.run(scrape_and_save(limit))
