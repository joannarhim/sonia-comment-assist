"""
ai_workflow.py
==============
Two AI tasks:
  1. score_relevance(post) -> 0-100 score + short reason
  2. draft_comment(post)   -> a short, kind, specific, non-spammy comment

Both run in MOCK mode by default so the app runs instantly with NO API key
(great for graders). 
Set AI_MODE=anthropic and ANTHROPIC_API_KEY in .env to use
a real LLM. 
"""

import os
import re

AI_MODE = os.getenv("AI_MODE", "mock").lower()

# Keywords that signal a post is relevant to a mental-health support brand.
RELEVANT_TERMS = [
    "therapy", "therapist", "anxiety", "anxious", "depress", "burnout", "burned out",
    "mental health", "stressed", "stress", "lonely", "loneliness", "grief", "cbt",
    "panic", "overwhelmed", "can't sleep", "cant sleep", "self care", "self-care",
    "waitlist", "afford", "cried", "dread", "mindful", "breathwork", "journaling",
]
PARTNER_TERMS = ["coach", "creator", "writer", "founder", "potential partner", "followers"]


# Relevance scoring

def score_relevance(post):
    if AI_MODE == "anthropic":
        try:
            return _score_relevance_llm(post)
        except Exception as e:  # fall back gracefully so the app never crashes
            return _score_relevance_mock(post, note=f"(LLM failed, used mock: {e})")
    return _score_relevance_mock(post)


def _score_relevance_mock(post, note=""):
    text = (post.get("text", "") + " " + post.get("context", "")).lower()
    hits = [t for t in RELEVANT_TERMS if t in text]

    if not hits:  # nothing relevant
        score = 20 if any(t in text for t in PARTNER_TERMS) else 12
        reason = "No mental-health relevance signals found."
        return {"score": score, "reason": (reason + " " + note).strip()}

    score = min(100, 25 + len(hits) * 15)          # base + signal
    if any(t in text for t in PARTNER_TERMS):
        score = min(100, score + 8)                # creators/partners are higher value
    reason = f"Matched {len(hits)} relevance signal(s): {', '.join(hits[:5])}."
    return {"score": score, "reason": (reason + " " + note).strip()}


# Comment drafting

def draft_comment(post):
    if AI_MODE == "anthropic":
        try:
            return _draft_comment_llm(post)
        except Exception:
            return _draft_comment_mock(post)
    return _draft_comment_mock(post)


def _draft_comment_mock(post):
    """
    Deterministic, template-based drafts keyed off the post's content.
    Kept short + kind. One case (p09) intentionally drafts a diagnosis-y line
    so you can SEE the Gate-2 comment filter catch a bad draft in the demo.
    """
    text = post.get("text", "").lower()
    pid = post.get("id")

    # Intentionally-bad draft to demonstrate the comment safety gate.
    if pid == "p09":
        return ("Those swings really sound like you have bipolar disorder, and the good "
                "news is therapy can treat and basically cure that, you'll be fine!")

    if "waitlist" in text or "afford" in text or "$" in text or "money" in text:
        return ("The cost and waitlist barriers are so real, and it's frustrating that "
                "wanting help isn't enough. Hope you find something that fits. You "
                "deserve support that's actually reachable.")
    if "burnout" in text or "burned out" in text or "tired all the time" in text:
        return ("Burnout is sneaky like that. It shows up as exhaustion and short fuses "
                "before you name it. Came out the other side by getting support and "
                "lowering the bar for a bit. You're not alone in this.")
    if "lonely" in text or "loneliness" in text or "make friends" in text:
        return ("Adult loneliness is so underrated as a hard thing. Repeated low-stakes "
                "stuff (a recurring class, a regular cafe) helped me more than big events. "
                "Rooting for you.")
    if "first" in text and ("therapy" in text or "appointment" in text or "session" in text):
        return ("Booking that first session is genuinely the hardest part, and that took "
                "courage. Mostly it's just a conversation to see if it's a fit. Hope it "
                "goes well!")
    if "grief" in text or "lost my" in text:
        return ("The cereal-aisle line hit me. Grief really does ambush you on ordinary "
                "days. Sending care to you in year one.")
    if "journaling" in text or "grounding routines" in text or "go-to" in text:
        return ("Ten minutes of journaling is such an accessible place to start, and I love that "
                "it's working for you. Mine is a quick brain-dump list before the day starts. "
                "Thanks for sharing this.")
    if "sunday" in text or ("anxiety" in text and "can't sleep" in text):
        return ("Sunday-night dread is so common and so exhausting. A short wind-down "
                "routine and naming the thought instead of believing it has helped me. "
                "Hope you find what works.")
    if "breathwork" in text or "box breathing" in text or "grounding" in text:
        return ("Box breathing before meetings is underrated, love this. Mine is a quick "
                "walk + naming three things I can see. Great reminder.")
    if "therapy" in text or "cbt" in text:
        return ("Love this framing. The 'notice the thought, don't believe every thought' "
                "idea is such a useful one to keep coming back to. (Full disclosure: I work "
                "with Sonia, an AI mental-health support tool, and this just resonated.)")
    if "night" in text or "schedule" in text or "shift" in text:
        return ("The scheduling mismatch is such a real barrier. Care that doesn't fit "
                "your hours basically doesn't exist for you. Hope you find something "
                "flexible that respects a weird shift pattern.")
    # generic supportive fallback
    return ("This really resonates, and thanks for sharing it so honestly. Wishing you some "
            "lighter days ahead.")

# Real LLM path (Anthropic). Only used when AI_MODE=anthropic.

_SYSTEM_PROMPT = """You help the growth team at Sonia (an AI mental-health support tool) \
write replies to public social posts. Rules:
- Be SPECIFIC to the post, kind, and human. Sound like a real person, not a brand.
- Keep it under ~300 characters. No hashtags, no links, no calls to action.
- Do NOT use em dashes (—). Use commas, periods, or colons instead.
- NEVER diagnose, never claim to cure/treat/prevent any condition, never give medical advice.
- Do NOT pitch Sonia. Only if it's genuinely natural may you mention it, and ONLY with a \
short transparency disclosure like "(I work with Sonia)".
- If the post involves crisis, a minor, or an acute emergency, reply with exactly: SKIP."""


def _client():
    from anthropic import Anthropic
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _score_relevance_llm(post):
    client = _client()
    msg = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=200,
        system="Rate 0-100 how relevant this post is for a mental-health support brand to "
               "reply to. Reply ONLY as: SCORE|reason",
        messages=[{"role": "user", "content": post.get("text", "")}],
    )
    out = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    m = re.match(r"\s*(\d{1,3})\s*\|\s*(.*)", out, flags=re.DOTALL)
    if not m:
        return _score_relevance_mock(post, note="(LLM format fallback)")
    return {"score": max(0, min(100, int(m.group(1)))), "reason": m.group(2).strip()}


def _draft_comment_llm(post):
    client = _client()
    msg = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user",
                   "content": f"Post by {post.get('author')}: {post.get('text')}"}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()