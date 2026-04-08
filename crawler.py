import asyncio
import os
import re
import httpx
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
import json


# ─────────────────────────────────────────────
# WEBSITE DEEP CRAWLER
# ─────────────────────────────────────────────

async def deep_crawl_website(website_url: str) -> dict:
    """
    Deep crawl company website.
    Visits homepage + contact + about + blog pages.
    Returns all useful text content found.
    """
    if not website_url or website_url == "None":
        return {"content": "", "emails": [], "pages_visited": []}

    collected_text = []
    collected_emails = set()
    pages_visited = []

    TARGET_KEYWORDS = ["contact", "about", "team", "blog", "news", "services", "solutions"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        try:
            page = await context.new_page()

            # Visit homepage first
            try:
                await page.goto(website_url, timeout=20000, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                content = await page.inner_text("body")
                collected_text.append(f"[HOMEPAGE]\n{content[:2000]}")
                pages_visited.append(website_url)

                # Find emails on homepage
                raw = await page.content()
                collected_emails.update(re.findall(
                    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw
                ))

                # Find sub-page links
                links = await page.locator("a[href]").all()
                sub_urls = set()
                for link in links:
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    full_url = urljoin(website_url, href)
                    # Only same domain
                    if urlparse(full_url).netloc != urlparse(website_url).netloc:
                        continue
                    if any(kw in href.lower() for kw in TARGET_KEYWORDS):
                        sub_urls.add(full_url)

                # Visit up to 4 sub-pages
                for sub_url in list(sub_urls)[:4]:
                    try:
                        await page.goto(sub_url, timeout=15000, wait_until="domcontentloaded")
                        await asyncio.sleep(1)
                        sub_content = await page.inner_text("body")
                        page_type = next(
                            (kw for kw in TARGET_KEYWORDS if kw in sub_url.lower()), "page"
                        )
                        collected_text.append(f"[{page_type.upper()}]\n{sub_content[:1500]}")
                        pages_visited.append(sub_url)

                        sub_raw = await page.content()
                        collected_emails.update(re.findall(
                            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', sub_raw
                        ))
                    except Exception:
                        continue

            except Exception as e:
                print(f"Homepage failed for {website_url}: {str(e)[:60]}")

        finally:
            await browser.close()

    # Filter junk emails
    clean_emails = [
        e for e in collected_emails
        if not any(x in e.lower() for x in [
            ".png", ".jpg", ".gif", "sentry", "example",
            "noreply", "no-reply", "support@sentry"
        ])
    ]

    full_content = "\n\n".join(collected_text)
    extracted = extract_company_details(full_content, website_url)

    return {
        "content": full_content,
        "emails": clean_emails,
        "pages_visited": pages_visited,
        "established_year": extracted["established_year"],
        "headquarters": extracted["headquarters"],
        "branches": extracted["branches"],
    }


def extract_company_details(text: str, website_url: str) -> dict:
    """
    Extract headquarters, established year and branch locations
    from crawled website text using regex patterns.
    """
    result = {
        "headquarters": None,
        "established_year": None,
        "branches": None,
    }

    # ── Established Year ──
    # Patterns: "Founded in 2005", "Established in 2005", "Since 2005", "Est. 2005"
    year_patterns = [
        r'[Ff]ounded\s+in\s+(\d{4})',
        r'[Ee]stablished\s+in\s+(\d{4})',
        r'[Ss]ince\s+(\d{4})',
        r'[Ee]st[\.\s]+(\d{4})',
        r'[Ii]ncorporated\s+in\s+(\d{4})',
        r'[Ss]tarted\s+in\s+(\d{4})',
        r'[Bb]egan\s+in\s+(\d{4})',
    ]
    for pattern in year_patterns:
        m = re.search(pattern, text)
        if m:
            year = m.group(1)
            if 1900 <= int(year) <= 2025:
                result["established_year"] = year
                break

    # ── Headquarters ──
    # Patterns: "Headquartered in Chennai", "HQ: Mumbai", "Head Office: Dubai"
    hq_patterns = [
        r'[Hh]eadquartered\s+in\s+([A-Z][a-zA-Z\s,]+?)[\.\n]',
        r'[Hh]ead(?:quarters|[\s-]*[Oo]ffice)\s*[:\-]\s*([A-Z][a-zA-Z\s,]+?)[\.\n]',
        r'[Hh][Qq]\s*[:\-]\s*([A-Z][a-zA-Z\s,]+?)[\.\n]',
        r'[Mm]ain\s+[Oo]ffice\s*[:\-]\s*([A-Z][a-zA-Z\s,]+?)[\.\n]',
        r'[Bb]ased\s+in\s+([A-Z][a-zA-Z\s,]+?)[\.\n,]',
    ]
    for pattern in hq_patterns:
        m = re.search(pattern, text)
        if m:
            val = m.group(1).strip().rstrip(",")
            if len(val) > 3 and "associated members" not in val.lower():
                result["headquarters"] = val[:100]
                break

    # ── Branch Locations ──
    # Look for "Our offices", "Our locations", "We are present in"
    branch_patterns = [
        r'[Oo]ur\s+[Oo]ffices?\s*[:\-]?\s*([A-Z][a-zA-Z\s,\|]+?)[\.\n]',
        r'[Oo]ur\s+[Ll]ocations?\s*[:\-]?\s*([A-Z][a-zA-Z\s,\|]+?)[\.\n]',
        r'[Pp]resent\s+in\s+([A-Z][a-zA-Z\s,&]+?)[\.\n]',
        r'[Oo]ffices?\s+in\s+([A-Z][a-zA-Z\s,&]+?)[\.\n]',
        r'[Ll]ocations?\s*[:\-]\s*([A-Z][a-zA-Z\s,\|]+?)[\.\n]',
        r'[Ww]e\s+operate\s+in\s+([A-Z][a-zA-Z\s,&]+?)[\.\n]',
    ]
    for pattern in branch_patterns:
        m = re.search(pattern, text)
        if m:
            val = m.group(1).strip().rstrip(",")
            if len(val) > 3:
                result["branches"] = val[:300]
                break

    return result


# ─────────────────────────────────────────────
# GOOGLE NEWS RSS CRAWLER
# ─────────────────────────────────────────────

async def search_google_news(company_name: str) -> str:
    """
    Search Google News RSS for recent company news.
    No API key needed.
    """
    if not company_name:
        return ""

    query = company_name.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(rss_url, follow_redirects=True)
            if response.status_code != 200:
                return ""

            content = response.text
            # Extract titles and descriptions from RSS
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', content)
            descriptions = re.findall(r'<description><!\[CDATA\[(.*?)\]\]></description>', content)

            news_items = []
            for i, title in enumerate(titles[1:6]):  # skip first (feed title), take 5
                desc = descriptions[i] if i < len(descriptions) else ""
                clean_desc = re.sub(r'<.*?>', '', desc)[:200]
                news_items.append(f"- {title}: {clean_desc}")

            return "\n".join(news_items) if news_items else "No recent news found."

    except Exception as e:
        print(f"News search failed for {company_name}: {str(e)[:60]}")
        return "News search unavailable."


# ─────────────────────────────────────────────
# LINKEDIN ACTIVITY SCRAPER
# ─────────────────────────────────────────────


async def scrape_linkedin_activity(linkedin_url: str, session_file: str) -> str:
    """
    Scrape recent LinkedIn posts from company page.
    Uses existing session.json for auth.
    """
    if not linkedin_url:
        return ""

    posts_url = f"{linkedin_url.rstrip('/')}/posts/"
    collected_posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        try:
            if session_file and os.path.exists(session_file):
                with open(session_file, "r") as f:
                    cookies = json.load(f)
                if isinstance(cookies, list):
                    await context.add_cookies(cookies)
                else:
                    await context.add_cookies(cookies.get("cookies", []))
            page = await context.new_page()
            await page.goto(posts_url, timeout=20000, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(2)

            # Extract post text
            post_els = await page.locator("span.break-words").all()
            for el in post_els[:5]:
                text = (await el.inner_text()).strip()
                if len(text) > 50:
                    collected_posts.append(text[:300])

        except Exception as e:
            print(f"LinkedIn activity scrape failed: {str(e)[:60]}")
        finally:
            await browser.close()

    return "\n\n".join(collected_posts) if collected_posts else "No recent posts found."
