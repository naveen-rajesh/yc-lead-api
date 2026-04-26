import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

OUTPUT_FILE = "data/companies.json"
BASE_URL = "https://www.ycombinator.com/companies"

async def scrape(limit=50):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Loading YC companies page...")
        await page.goto(BASE_URL)
        await page.wait_for_timeout(5000)

        links = await page.eval_on_selector_all(
            "a[href*='/companies/']",
            "elements => elements.map(e => e.href)"
        )

        links = list(dict.fromkeys(links))[:limit]

        for i, url in enumerate(links, 1):
            try:
                print(f"[{i}/{limit}] Scraping {url}")
                await page.goto(url)
                await page.wait_for_timeout(3000)

                # 🔥 FIX 1: CLEAN NAME FROM URL
                slug = url.split("/")[-1]
                name = slug.replace("-", " ").title()

                # ❌ Skip junk entries
                if "jobs" in name.lower():
                    continue

                # 🔥 FIX 2: TAGLINE CLEAN
                tagline = await page.evaluate("""() => {
                    const el = document.querySelector('h2');
                    return el ? el.innerText.trim() : "";
                }""")

                # 🔥 FIX 3: DESCRIPTION
                description = await page.evaluate("""() => {
                    const el = document.querySelector('p');
                    return el ? el.innerText.trim() : "";
                }""")

                # 🔥 FIX 4: FOUNDERS (CLEAN)
                founders = await page.evaluate("""() => {
                    const names = [];
                    document.querySelectorAll('a[href*="/people/"]').forEach(a => {
                        const text = a.innerText.trim();
                        if (
                            text &&
                            text.length < 40 &&
                            text.split(" ").length <= 3 &&
                            !text.toLowerCase().includes("yc")
                        ) {
                            names.push(text);
                        }
                    });
                    return [...new Set(names)].slice(0, 3);
                }""")

                # 🔥 FIX 5: WEBSITE
                website = await page.evaluate("""() => {
                    const a = document.querySelector('a[href^="http"]');
                    return a ? a.href : "";
                }""")

                # 🔥 FIX 6: TECH STACK (basic detection)
                tech_stack = []
                if description:
                    if "react" in description.lower(): tech_stack.append("React")
                    if "aws" in description.lower(): tech_stack.append("AWS")
                    if "cloud" in description.lower(): tech_stack.append("Cloud")

                company = {
                    "id": i,
                    "name": name,
                    "tagline": tagline,
                    "description": description,
                    "batch": "",
                    "website": website,
                    "linkedin": "",
                    "twitter": "",
                    "founders": founders,
                    "tags": [],
                    "tech_stack": tech_stack,
                    "yc_url": url,
                    "email": "",
                    "scraped_at": datetime.utcnow().isoformat(),
                }

                results.append(company)

            except Exception as e:
                print("Error:", e)
                continue

        await browser.close()

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved {len(results)} companies")


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    asyncio.run(scrape(limit))
