import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

ANYTHING_LLM_URL =  "http://192.168.1.51:3001"
ANYTHING_LLM_TOKEN = "21Y0K2Q-DEDM82D-GRBGH34-W8GGAQX"
WORKSPACE = "my-workspace"
async def ask_llm(prompt: str, expect_json: bool = True) -> str:
    """
    Send a prompt to AnythingLLM and return the response text.
    """
    url = f"{ANYTHING_LLM_URL}/api/v1/workspace/{WORKSPACE}/chat"
    headers = {
        "Authorization": f"Bearer {ANYTHING_LLM_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": prompt,
        "mode": "chat"
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                print(f"LLM error {response.status_code}: {response.text[:100]}")
                return ""

            data = response.json()
            text = data.get("textResponse", "")

            if expect_json:
                # Strip markdown code fences if present
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                text = text.strip()

            return text

    except Exception as e:
        print(f"LLM request failed: {str(e)[:80]}")
        return ""


async def generate_intel_brief(
    company_name: str,
    company_description: str,
    website_content: str,
    linkedin_posts: str,
    news: str
) -> dict:
    """
    Generate a structured Intel Brief for a lead using LLM.
    Returns a dict with summary, pain_points, recent_activity, hook, tone.
    """
    prompt = f"""You are a B2B sales intelligence analyst. Analyze this company data and generate a structured Intel Brief.

COMPANY: {company_name}

LINKEDIN DESCRIPTION:
{company_description or 'Not available'}

WEBSITE CONTENT:
{website_content[:3000] if website_content else 'Not available'}

RECENT LINKEDIN POSTS:
{linkedin_posts[:1000] if linkedin_posts else 'Not available'}

RECENT NEWS:
{news[:500] if news else 'Not available'}

Generate a sales Intel Brief. Output ONLY valid JSON with these exact keys:
{{
  "summary": "2 sentence summary of what this company does and their current situation",
  "pain_points": ["specific pain point 1", "specific pain point 2", "specific pain point 3"],
  "recent_activity": "one specific recent thing they posted or announced",
  "hook": "one personalized opening line referencing their recent activity or situation",
  "tone": "formal or casual based on their communication style",
  "best_angle": "which angle to use: cost_saving / efficiency / growth / compliance / innovation"
}}

Be specific. No generic statements. Base everything on the actual data provided."""

    result_text = await ask_llm(prompt, expect_json=True)

    try:
        result = json.loads(result_text)
        return result
    except Exception:
        # Fallback if LLM returns bad JSON
        return {
            "summary": company_description[:200] if company_description else "No description available.",
            "pain_points": ["Operational efficiency", "Digital transformation", "Cost optimization"],
            "recent_activity": "No recent activity found.",
            "hook": f"I came across {company_name} and noticed your work in the industry.",
            "tone": "formal",
            "best_angle": "efficiency"
        }


async def generate_connection_hook(
    company_name: str,
    contact_name: str,
    intel_brief: dict
) -> str:
    """
    Generate a short LinkedIn connection request message.
    Must be under 300 characters (LinkedIn limit).
    """
    prompt = f"""Write a LinkedIn connection request message for a cold outreach.

Target: {contact_name or 'the decision maker'} at {company_name}
Their recent activity: {intel_brief.get('recent_activity', 'working in their industry')}
Best angle: {intel_brief.get('best_angle', 'efficiency')}

Rules:
- Under 280 characters total
- Reference ONE specific thing about their company
- No pitching, no selling — just connecting
- Sound human, not robotic
- No emojis

Output ONLY the message text, nothing else."""

    result = await ask_llm(prompt, expect_json=False)

    # Enforce character limit
    if len(result) > 280:
        result = result[:277] + "..."

    return result.strip()
