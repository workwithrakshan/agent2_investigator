import asyncio
import random
import json
import os
from datetime import datetime, date
from playwright.async_api import async_playwright
from app.database import SessionLocal
from app.models import Lead

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")
DAILY_LIMIT = 20  # LinkedIn safety limit


def get_requests_sent_today() -> int:
    """Count LinkedIn requests sent today from DB."""
    db = SessionLocal()
    today_start = datetime.combine(date.today(), datetime.min.time())
    count = db.query(Lead).filter(
        Lead.linkedin_requested_at >= today_start
    ).count()
    db.close()
    return count


async def send_connection_request(
    contact_linkedin_url: str,
    hook_message: str,
    lead_id: int
) -> bool:
    """
    Send a LinkedIn connection request with personalized message.
    Returns True if sent successfully.
    """
    if not contact_linkedin_url:
        print(f"No LinkedIn URL for lead {lead_id}, skipping connection request.")
        return False

    # Check daily limit
    sent_today = get_requests_sent_today()
    if sent_today >= DAILY_LIMIT:
        print(f"Daily LinkedIn limit reached ({DAILY_LIMIT}). Skipping.")
        return False

    if not os.path.exists(SESSION_FILE):
        print("session.json not found. Skipping LinkedIn connection.")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        try:
            # Load session cookies
            session_data = json.loads(open(SESSION_FILE).read())
            if "cookies" in session_data:
                await context.add_cookies(session_data["cookies"])

            page = await context.new_page()

            # Go to contact's LinkedIn profile
            profile_url = contact_linkedin_url.rstrip("/")
            print(f"Opening LinkedIn profile: {profile_url}")
            await page.goto(profile_url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(random.randint(3, 6))

            # Click Connect button
            connect_btn = page.locator("button:has-text('Connect')").first
            if await connect_btn.count() == 0:
                # Try More > Connect
                more_btn = page.locator("button:has-text('More')").first
                if await more_btn.count() > 0:
                    await more_btn.click()
                    await asyncio.sleep(1)
                    connect_btn = page.locator("li:has-text('Connect')").first

            if await connect_btn.count() == 0:
                print(f"Connect button not found for lead {lead_id}")
                return False

            await connect_btn.click()
            await asyncio.sleep(2)

            # Click "Add a note"
            add_note_btn = page.locator("button:has-text('Add a note')").first
            if await add_note_btn.count() > 0:
                await add_note_btn.click()
                await asyncio.sleep(1)

                # Type the hook message
                textarea = page.locator("textarea[name='message']").first
                if await textarea.count() > 0:
                    await textarea.fill(hook_message)
                    await asyncio.sleep(1)

            # Click Send
            send_btn = page.locator("button:has-text('Send')").first
            if await send_btn.count() > 0:
                await send_btn.click()
                await asyncio.sleep(2)
                print(f"Connection request sent to lead {lead_id}")
                return True
            else:
                print(f"Send button not found for lead {lead_id}")
                return False

        except Exception as e:
            print(f"LinkedIn connection failed for lead {lead_id}: {str(e)[:80]}")
            return False
        finally:
            await browser.close()
