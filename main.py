from fastapi import FastAPI, BackgroundTasks
from sqlalchemy import text
from app.database import Base, engine, SessionLocal
from app.models import Lead
import asyncio


# ── DB INIT ──
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agent 2: Investigator", version="1.0")

# ── STATUS TRACKER ──
agent_status = {
    "running": False,
    "message": "idle",
    "processed": 0,
    "success": 0,
    "failed": 0
}


# ── BACKGROUND RUNNER ──
def run_agent():
    global agent_status
    agent_status = {
        "running": True,
        "message": "Investigating NEW leads...",
        "processed": 0,
        "success": 0,
        "failed": 0
    }
    try:
        from investigator import run_investigator
        result = asyncio.run(run_investigator())
        agent_status = {
            "running": False,
            "message": "Complete",
            "processed": result["processed"],
            "success": result["success"],
            "failed": result["failed"]
        }
    except Exception as e:
        agent_status = {
            "running": False,
            "message": f"Error: {str(e)}",
            "processed": 0,
            "success": 0,
            "failed": 0
        }


# ── ENDPOINTS ──

@app.post("/agent2/run")
def start_agent(background_tasks: BackgroundTasks):
    """n8n calls this every 6 hours to investigate NEW leads."""
    if agent_status["running"]:
        return {"status": "already_running"}
    background_tasks.add_task(run_agent)
    return {"status": "started"}


@app.get("/agent2/status")
def get_status():
    """n8n polls this until running=false."""
    return agent_status


@app.get("/agent2/leads")
def get_researched_leads():
    """View all RESEARCHED leads ready for Agent 3."""
    db = SessionLocal()
    leads = db.query(Lead).filter(Lead.status == "RESEARCHED").all()
    db.close()
    return {
        "count": len(leads),
        "leads": [
            {
                "id": l.id,
                "company_name": l.company_name,
                "contact_email": l.contact_email,
                "industry": l.industry,
                "company_size": l.company_size,
                "location": l.location,
                "established_year": l.established_year,
                "headquarters": l.headquarters,
                "branches": l.branches,
                "intel_brief": l.intel_brief,
                "pain_points": l.pain_points,
                "recent_activity": l.recent_activity,
                "hook_used": l.hook_used,
                "linkedin_connected": l.linkedin_connected,
                "status": l.status
            }
            for l in leads
        ]
    }


@app.get("/agent2/stats")
def get_stats():
    """Full pipeline stats."""
    db = SessionLocal()
    statuses = [
        "NEW", "INVESTIGATING", "RESEARCHED", "CONTACTED",
        "FOLLOW_UP_1", "FOLLOW_UP_2", "FOLLOW_UP_3",
        "REPLIED", "PAUSED", "CLOSED_WON", "CLOSED_LOST"
    ]
    stats = {s: db.query(Lead).filter(Lead.status == s).count() for s in statuses}
    stats["TOTAL"] = db.query(Lead).count()
    db.close()
    return stats


@app.get("/agent2/lead/{lead_id}")
def get_lead_detail(lead_id: int):
    """View full intel brief for one lead."""
    db = SessionLocal()
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    db.close()
    if not lead:
        return {"error": "Lead not found"}
    return {
        "id": lead.id,
        "company_name": lead.company_name,
        "company_website": lead.company_website,
        "linkedin_url": lead.linkedin_url,
        "contact_email": lead.contact_email,
        "industry": lead.industry,
        "company_size": lead.company_size,
        "location": lead.location,
        "established_year": lead.established_year,
        "headquarters": lead.headquarters,
        "branches": lead.branches,
        "contact_name": lead.contact_name,
        "contact_linkedin": lead.contact_linkedin,
        "intel_brief": lead.intel_brief,
        "pain_points": lead.pain_points,
        "recent_activity": lead.recent_activity,
        "hook_used": lead.hook_used,
        "linkedin_connected": lead.linkedin_connected,
        "linkedin_requested_at": str(lead.linkedin_requested_at),
        "status": lead.status
    }
