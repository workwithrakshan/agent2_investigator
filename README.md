# Agent 2: The Investigator

Picks up NEW leads from DB, deep crawls their website, generates Intel Brief using LLM,
sends LinkedIn connection request, saves everything, sets status=RESEARCHED.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Copy session.json from Agent 1
```
copy ..\agent1_archivist\session.json session.json
```

## Update .env
- Set ANYTHINGLLM_TOKEN to your actual token
- Confirm DATABASE_URL is correct

## Start
```
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

## Endpoints
- POST /agent2/run         → start investigating NEW leads
- GET  /agent2/status      → check if running
- GET  /agent2/leads       → view RESEARCHED leads
- GET  /agent2/stats       → full pipeline stats
- GET  /agent2/lead/{id}   → full detail for one lead

## What gets stored per lead
- intel_brief       → LLM-generated company summary
- pain_points       → JSON array of 3 specific pain points
- recent_activity   → latest news/post found
- hook_used         → personalized LinkedIn message sent
- linkedin_connected → True if connection request sent
- status            → NEW → RESEARCHED

## n8n Trigger
Schedule: Every 6 hours
POST http://host.docker.internal:8002/agent2/run
