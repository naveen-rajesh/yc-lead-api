# 🚀 PRODUCTION-READY YC SCRAPER (API-READY, HIGH-VALUE DATA)

import asyncio
import json
import re
import random
import logging
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent / "companies.json"

# XPath for company name (primary)
NAME_XPATH = "/html/body/div/div[2]/div/div[2]/div[1]/div[1]/div[2]/div[1]/div"

# Regex
BATCH_RE = re.compile(r"(Winter|Summer|Spring|Fall)\s+\d{4}", re.I)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# -------- NAME EXTRACTION --------
async def get_company_name(page, slug):
    try:
        el = page.locator(f"xpath={NAME_XPATH}")
        if await el.count() > 0:
            text = (await el.first.inner_text()).strip()
            if text and not text.lower().startswith("jobs") and "founder" not in text.lower():
                return text
    except:
        pass

    try:
        h1 = page.locator("h1")
        if await h1.count() > 0:
            return (await h1.first.inner_text()).strip()
    except:
        pass

    return slug.replace("-", " ").title()


# -------- PARSE TEXT DATA --------
def parse_text(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    tagline = ""
    batch = ""
    description = ""
    tags = []

    for line in lines:
        if not batch and BATCH_RE.search(line):
            batch = line

        if not tagline and 20 < len(line) < 120 and not line.startswith("http"):
            tagline = line

        if line.isupper() and len(line) < 40:
            tags.append(line.title())

    description = " ".join(lines[:5])

    return tagline, batch, description, tags[:5]


# -------- EMAIL SCRAPER --------
async def extract_emails(ctx, url):
    emails = set()
    try:
        page = await ctx.new_page()
        await page.goto(url, timeout=15000)
        html = await page.content()
        found = EMAIL_RE.findall(html)
        for e in found:
            if not e.endswith((".png", ".jpg")):
                emails.add(e)
        await page.close()
    except:
        pass
    return list(emails)[:3]


# -------- TECH DETECTION --------
async def detect_tech(ctx, url):
    tech = set()
    try:
        page = await ctx.new_page()
        resp = await page.goto(url, timeout=15000)
        html = (await page.content()).lower()

        if "react" in html:
            tech.add("React")
        if "next" in html:
            tech.add("Next.js")
        if "cloudflare" in html:
            tech.add("Cloudflare")
        if "aws" in html or "amazonaws" in html:
            tech.add("AWS")

        if resp:
            server = resp.headers.get("server", "").lower()
            if "nginx" in server:
                tech.add("Nginx")

        await page.close()
    except:
        pass
    return list(tech)


# -------- MAIN SCRAPER --------
async def scrape(batch_size=20):
    results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        await page.goto("https://www.ycombinator.com/companies")
        await page.wait_for_timeout(4000)

        for _ in range(8):
            await page.keyboard.press("End")
            await page.wait_for_timeout(1200)

        hrefs = await page.evaluate("""() => {
            const links = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href');
                if (h && h.startsWith('/companies/')) links.push(h);
            });
            return [...new Set(links)];
        }""")

        for i, href in enumerate(hrefs[:batch_size]):
            url = "https://www.ycombinator.com" + href
            slug = href.split("/")[-1]

            try:
                log.info(f"[{i+1}] {url}")
                await page.goto(url)
                await page.wait_for_timeout(2500)

                name = await get_company_name(page, slug)
                body = await page.evaluate("() => document.body.innerText")

                tagline, batch, description, tags = parse_text(body)

                website = await page.evaluate("""() => {
                    const a = document.querySelector('a[rel="noreferrer"]');
                    return a ? a.href : '';
                }""")

                linkedin = await page.evaluate("""() => {
                    const a = document.querySelector('a[href*="linkedin.com"]');
                    return a ? a.href : '';
                }""")

                twitter = await page.evaluate("""() => {
                    const a = document.querySelector('a[href*="twitter.com"], a[href*="x.com"]');
                    return a ? a.href : '';
                }""")

                founders = await page.evaluate("""() => {
                    const arr = [];
                    document.querySelectorAll('a[href*="/people/"]').forEach(a => {
                        const t = a.innerText.trim();
                        if (t.length < 50) arr.push(t);
                    });
                    return [...new Set(arr)].slice(0,5);
                }""")

                emails = []
                tech = []

                if website:
                    emails = await extract_emails(ctx, website)
                    tech = await detect_tech(ctx, website)

                company = {
                    "id": i+1,
                    "name": name,
                    "tagline": tagline,
                    "description": description,
                    "batch": batch,
                    "website": website,
                    "linkedin": linkedin,
                    "twitter": twitter,
                    "founders": founders,
                    "tags": tags,
                    "emails": emails,
                    "tech_stack": tech,
                    "yc_url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                }

                results.append(company)
                log.info(f"✓ {name} | {batch}")

                await asyncio.sleep(random.uniform(0.5,1.2))

            except Exception as e:
                log.error(f"✗ {url}: {e}")

        await browser.close()

    with open(DATA_FILE, "w") as f:
        json.dump(results, f, indent=2)

    log.info(f"Saved {len(results)} companies")


if __name__ == "__main__":
    asyncio.run(scrape(10))
