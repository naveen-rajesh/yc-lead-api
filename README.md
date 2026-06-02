# YC Startup Leads API

Low-latency FastAPI service for searching YC company data, finding high-value startup leads, and exposing clean metadata facets for prospecting tools.

## What changed for production

- No browser scraping on customer requests.
- Data is loaded from `data/companies.json` once and reused from memory.
- `/companies` supports search, pagination, and filters for `tech`, `industry`, `batch`, `status`, `location`, and `min_team_size`.
- `/leads/high-value` returns scored leads sorted by usefulness.
- `/metadata` returns facets that make the API easier to integrate into apps.
- RapidAPI traffic can be validated with `RAPIDAPI_PROXY_SECRET`.
- Vercel deployment is configured through `vercel.json` and `api/index.py`.

## Endpoints

All business endpoints require either `X-API-Key` or RapidAPI proxy headers. `/health` and `/healthz` are public.

### `GET /companies`

Query YC companies.

Parameters:

- `q`: full-text search across name, tagline, description, industry, tags, and location
- `tech`: tag/category filter
- `industry`: industry filter
- `batch`: YC batch filter
- `status`: company status filter
- `location`: location filter
- `min_team_size`: minimum team size
- `page`: page number, default `1`
- `limit`: page size, default `20`, max `100`

Example:

```bash
curl "https://your-domain.vercel.app/companies?q=ai&industry=B2B&limit=10" \
  -H "X-API-Key: demo_key_12345"
```

### `GET /company/{id}`

Fetch one company by YC id.

### `GET /leads/high-value`

Returns companies with a website and useful enrichment fields, sorted by `lead_score`.

### `GET /metadata`

Returns available industries, batches, statuses, company count, and data update time.

### `GET /health`

Public uptime and data-count check.

## Local Development

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/uvicorn api.main:app --reload
```

Run tests:

```bash
venv/bin/pytest
```

Refresh the bundled YC dataset offline:

```bash
venv/bin/python scraper/yc_scraper.py 500
```

Commit the refreshed `data/companies.json` before deploying. This keeps Vercel fast because requests do not scrape live pages.

## Environment Variables

- `DIRECT_API_KEYS`: comma-separated direct API keys. Defaults to `demo_key_12345`.
- `DEFAULT_TIER`: rate-limit tier for direct and RapidAPI users. Defaults to `free`.
- `RAPIDAPI_PROXY_SECRET`: shared secret configured in RapidAPI. When set, RapidAPI requests must include `X-RapidAPI-Proxy-Secret`.

## Deploy to Vercel

```bash
npx vercel@latest link
npx vercel@latest deploy --prod
```

Set production environment variables in Vercel before publishing through RapidAPI:

```bash
npx vercel@latest env add RAPIDAPI_PROXY_SECRET production
npx vercel@latest env add DIRECT_API_KEYS production
```

