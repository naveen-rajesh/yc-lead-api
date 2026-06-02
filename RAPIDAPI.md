# RapidAPI Listing Guide

## Base URL

Use the production Vercel URL:

```text
https://your-domain.vercel.app
```

Configure RapidAPI to forward requests to this URL and set a private proxy secret. Add the same value to Vercel as `RAPIDAPI_PROXY_SECRET`.

## Authentication

RapidAPI should send:

- `X-RapidAPI-Key`
- `X-RapidAPI-Proxy-Secret`

Do not ask RapidAPI customers to manage a separate `X-API-Key`. RapidAPI handles subscriptions, billing, quotas, and user identity.

## Suggested Public Description

YC Startup Leads API provides searchable Y Combinator company data for sales prospecting, market research, enrichment, and startup discovery. Search by keyword, industry, batch, status, location, team size, and category tags. Use the high-value leads endpoint to quickly surface companies with stronger sales signals.

## Suggested Endpoints for RapidAPI

### Search Companies

`GET /companies`

Required headers are handled by RapidAPI. Recommended examples:

```text
/companies?q=ai&limit=10
/companies?industry=B2B&min_team_size=10
/companies?batch=Winter%202024&status=Active
```

### Company Details

`GET /company/{id}`

### High-Value Leads

`GET /leads/high-value`

Recommended example:

```text
/leads/high-value?industry=B2B&min_team_size=5&limit=20
```

### Metadata

`GET /metadata`

Use this for dropdown filters in customer apps.

## Suggested Pricing

RapidAPI should own billing and quota enforcement. Keep app-side limits as a backstop only.

### Free

- Price: `$0`
- Quota: `100 requests/month`
- Rate limit: `30 requests/minute`
- Good for trial users and integration testing.

### Starter

- Price: `$9/month`
- Quota: `5,000 requests/month`
- Rate limit: `120 requests/minute`
- Good for indie tools and small prospecting workflows.

### Growth

- Price: `$29/month`
- Quota: `50,000 requests/month`
- Rate limit: `600 requests/minute`
- Good for CRM enrichment and sales automation.

### Business

- Price: `$99/month`
- Quota: `250,000 requests/month`
- Rate limit: `1,500 requests/minute`
- Add priority support and custom refresh cadence.

## Recommended RapidAPI Tests

After the Vercel URL is live, create tests in the RapidAPI dashboard:

1. `GET /health` should return `200` and `status: ok`.
2. `GET /companies?limit=1` should return `200`, `total`, `page`, `limit`, and `results`.
3. `GET /metadata` should return industries, batches, and statuses.
4. `GET /leads/high-value?limit=1` should return `lead_score`.
5. A request without the RapidAPI proxy secret should return `403` if `RAPIDAPI_PROXY_SECRET` is configured.

## Listing Quality Checklist

- Use `/docs` from the Vercel deployment to copy exact request and response schemas.
- Add code snippets for JavaScript, Python, and cURL.
- Mention that data is bundled for speed and refreshed offline.
- Do not promise email addresses unless an enrichment provider is added.
- Do not claim real-time YC updates unless a scheduled refresh pipeline is added.

