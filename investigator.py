import asyncio
import random
import json
import os
import sys
from datetime import datetime
from app.database import SessionLocal
from app.models import Lead
from crawler import deep_crawl_website, search_google_news, scrape_linkedin_activity
from llm_client import generate_intel_brief, generate_connection_hook
from linkedin_connect import send_connection_request

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")
BATCH_SIZE = None  # Process all NEW leads per run
async def process_lead(lead_id: int):
    """
    Fully investigate one lead.
    - Deep crawl website
    - Search news
    - Scrape LinkedIn activity
    - Generate Intel Brief with LLM
    - Generate connection hook
    - Send LinkedIn connection request
    - Save everything to DB
    - Set status = RESEARCHED
    """
    db = SessionLocal()

    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            print(f"Lead {lead_id} not found.")
            return

        print(f"\nInvestigating: {lead.company_name} (ID: {lead_id})")

        # ── STEP 1: Deep crawl website ──
        print(f"  Deep crawling: {lead.company_website}")
        website_data = await deep_crawl_website(lead.company_website)

        # Update email if we found a better one
        if website_data["emails"] and not lead.contact_email:
            lead.contact_email = website_data["emails"][0]
            print(f"  Found email: {lead.contact_email}")

        # ── STEP 2: Search Google News ──
        print(f"  Searching news for: {lead.company_name}")
        news = await search_google_news(lead.company_name)

        # ── STEP 3: Scrape LinkedIn activity ──
        print(f"  Scraping LinkedIn activity...")
        linkedin_posts = await scrape_linkedin_activity(lead.linkedin_url, SESSION_FILE)

        # ── STEP 4: Generate Intel Brief with LLM ──
        print(f"  Generating Intel Brief...")
        intel = await generate_intel_brief(
            company_name=lead.company_name,
            company_description=lead.company_description,
            website_content=website_data["content"],
            linkedin_posts=linkedin_posts,
            news=news
        )

        # ── STEP 5: Generate LinkedIn connection hook ──
        print(f"  Generating connection hook...")
        hook = await generate_connection_hook(
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            intel_brief=intel
        )

        # ── STEP 6: Send LinkedIn connection request ──
        connection_sent = False
        if lead.contact_linkedin and not lead.linkedin_requested_at:
            print(f"  Sending LinkedIn connection request...")
            connection_sent = await send_connection_request(
                contact_linkedin_url=lead.contact_linkedin,
                hook_message=hook,
                lead_id=lead.id
            )
        else:
            print(f"  Skipping LinkedIn (no URL or already requested)")

        # ── STEP 7: Save everything to DB ──
        # ── STEP 7: Save everything to DB ──
        lead.intel_brief = intel.get("summary", "") if intel else ""
        lead.pain_points = json.dumps(intel.get("pain_points", [])) if intel else "[]"
        lead.recent_activity = intel.get("recent_activity", "") if intel else ""
        lead.hook_used = hook if hook else ""

        # Fill nulls from website crawl if Agent 1 missed them
        if not lead.established_year and website_data.get("established_year"):
            lead.established_year = website_data["established_year"]
        if not lead.headquarters and website_data.get("headquarters"):
            lead.headquarters = website_data["headquarters"]
            lead.location = website_data["headquarters"]
        if not lead.branches and website_data.get("branches"):
            lead.branches = website_data["branches"]

        if connection_sent:
            lead.linkedin_connected = True
            lead.linkedin_requested_at = datetime.now()

        lead.status = "RESEARCHED"
        lead.status_updated_at = datetime.now()
        lead.updated_at = datetime.now()

        db.commit()
        print(f"  Done: {lead.company_name} → RESEARCHED")
        return True

    except Exception as e:
        print(f"  Error processing lead {lead_id}: {str(e)[:100]}")
        # Revert to NEW so it retries next run
        try:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead and lead.status == "INVESTIGATING":
                lead.status = "NEW"
                db.commit()
        except:
            pass
        return False

    finally:
        db.close()


async def run_investigator():
    """
    Main Agent 2 function.
    Picks up NEW leads, investigates them, saves to DB.
    Returns counts.
    """
    db = SessionLocal()

    # Fetch NEW leads — lock them immediately to INVESTIGATING
    leads = db.query(Lead).filter(
        Lead.status == "NEW"
    ).order_by(Lead.scraped_at.asc()).all()

    if not leads:
        print("No NEW leads to investigate.")
        db.close()
        return {"processed": 0, "success": 0, "failed": 0}

    # Lock all fetched leads immediately (prevents duplicate processing)
    lead_ids = [l.id for l in leads]
    for lead in leads:
        lead.status = "INVESTIGATING"
    db.commit()
    db.close()

    print(f"Locked {len(lead_ids)} leads for investigation.")

    success_count = 0
    fail_count = 0

    for lead_id in lead_ids:
        result = await process_lead(lead_id)
        if result:
            success_count += 1
        else:
            fail_count += 1

        # Rate limit safety between leads
        wait = random.randint(20, 45)
        print(f"  Waiting {wait}s before next lead...")
        await asyncio.sleep(wait)

    print(f"\nInvestigation complete. Success: {success_count} | Failed: {fail_count}")
    return {
        "processed": len(lead_ids),
        "success": success_count,
        "failed": fail_count
    }


# ─────────────────────────────────────────────
# STANDALONE RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_investigator())
