"""
safety.py
=========
The safety layer is the most important part of this tool. Because Sonia is a
mental-health product, commenting on the wrong post (or with the wrong wording)
is a real-world harm and a brand/platform risk. We run TWO gates:

  1. should_engage(post)      -> decide if we may engage with a post AT ALL
  2. check_comment(comment)   -> decide if a *drafted comment* is safe to post

Both gates are deliberately conservative: when unsure, we BLOCK or FLAG and send
it to a human. False positives (flagging a safe post) are cheap. False negatives
(commenting on a suicidal teenager's post with a product plug) are catastrophic.

This implementation uses transparent keyword/heuristic rules so a reviewer can
see exactly *why* something was flagged. In production you would add an LLM
classifier as an additional layer (see README "What I'd build next").
"""

import re

# ---------------------------------------------------------------------------
# Rule sets. Kept readable on purpose so a non-engineer can audit them.
# ---------------------------------------------------------------------------

CRISIS_PATTERNS = [
    r"\bkill myself\b", r"\bend it\b", r"\bend my life\b", r"\bsuicid",
    r"\bdon'?t want to (be here|live|wake up)\b", r"\bwant to die\b",
    r"\bno (point|reason) (in|to) (waking|living|going on)\b",
    r"\bself.?harm\b", r"\bcut(ting)? myself\b", r"\boverdose\b",
    r"\bnothing (helps|matters) anymore\b",
]

# Softer than crisis: distress that COULD be serious but isn't explicit ideation.
# These FLAG (not block) for careful human review rather than auto-engaging.
# NOTE: this is a deliberately small list. Truly paraphrased crisis (e.g. "I can't
# keep doing this", "I'm just really done") is NOT reliably catchable by keywords and
# is the motivating case for an LLM safety classifier (see README limitations).
AMBIGUOUS_DISTRESS_PATTERNS = [
    r"\bdrowning\b", r"\bcan'?t (cope|go on|take (it|this) anymore)\b",
    r"\bfalling apart\b", r"\bat my (breaking point|limit)\b",
    r"\bso overwhelmed\b.{0,30}\bcan'?t (think|breathe|function)\b",
]

MINOR_PATTERNS = [
    r"\bi'?m \d{1,2}\b",            # "im 15" / "i'm 16"  (validated below)
    r"\b(\d{1,2}) ?(yo|y/o|years? old)\b",
    r"\b(high ?school|middle ?school|8th grade|9th grade|10th grade|11th grade|12th grade|sophomore|freshman|junior year|senior year)\b",
    r"\bmy (teen|kid|son|daughter) is \d{1,2}\b",
]

# Posts describing acute, in-progress emergencies we should never "growth comment" on.
INAPPROPRIATE_INTERVENTION_PATTERNS = [
    r"\b(in the|at the) (er|hospital|psych ward)\b",
    r"\b(being|getting) (hit|abused|beaten)\b",
    r"\bhitting me\b", r"\bhe hits me\b", r"\bdomestic violence\b",
    r"\bcall(ing)? 911\b", r"\brestraining order\b",
]

# Sharing of identifying / dangerous private info -> too sensitive to engage publicly.
PRIVACY_PATTERNS = [
    r"\b(home|work) address\b", r"\bmy address is\b",
    r"\bphone number is\b", r"\bsocial security\b", r"\bssn\b",
    r"\bmy full name\b", r"\bmy (apartment|apt|unit) (number|#|no)\b",
    r"\bwhere i (work|live)\b.{0,40}\bin case\b",
    r"\b(full name|address).{0,30}\bin case (anything|something) happens\b",
]

# Posts about medication changes / acute medical decisions -> never give medical advice.
MEDICAL_RISK_PATTERNS = [
    r"\b(stop|stopping|quit|quitting|come off|coming off|wean(ing)? off|taper) .{0,25}\b(antidepressant|ssri|meds?|medication|prozac|zoloft|lexapro|wellbutrin|lithium)\b",
    r"\bcold turkey\b",
    r"\b(double|skip|increase|decrease|change) (my|the) (dose|dosage|meds?|medication)\b",
    r"\bshould i (stop|quit|change) .{0,20}\b(meds?|medication|antidepressant)\b",
]

OFFTOPIC_PATTERNS = [  # not unsafe, just irrelevant to a mental-health brand
    r"\bcrypto\b", r"\b10x\b", r"\bbuy the dip\b", r"\bnft\b", r"\bairdrop\b",
]

SPAM_PATTERNS = [  # used on the *post* (low value) and the *comment* (we must not emit)
    r"\bdm me\b", r"\blink in bio\b", r"\bflash sale\b", r"\bclick fast\b",
    r"\bguaranteed results\b", r"\blimited spots\b", r"%\s*off\b", r"\bbuy now\b",
]

# Language a comment must NEVER use: medical claims / diagnosis / cure / prevention.
MEDICAL_CLAIM_PATTERNS = [
    r"\bcure(s|d)?\b", r"\btreat(s|ment)?\b", r"\bdiagnos", r"\bprevent(s|ion)?\b",
    r"\byou (have|are suffering from) (depression|bipolar|anxiety disorder|ptsd|ocd)\b",
    r"\bthis will (fix|heal|cure)\b", r"\bclinically proven to\b", r"\bguaranteed to help\b",
    r"\byou should stop (taking|your) medication\b",
]

CRISIS_RESOURCE_NOTE = (
    "CRISIS: do not comment. If a human chooses to respond at all, respond only "
    "with care + crisis resources (e.g. 988 Suicide & Crisis Lifeline in the US, "
    "or local emergency services). Never insert product messaging."
)


def _any(patterns, text):
    """Return the list of patterns that matched (for transparent reporting)."""
    hits = []
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            hits.append(p)
    return hits


def _looks_like_minor(text):
    """Validate age-like matches so '@studyhard_2027' or 'I'm 32' don't false-trigger."""
    # explicit school-age phrasing
    if _any([r"\b(high ?school|middle ?school|8th grade|9th grade|10th grade|11th grade|12th grade|sophomore|freshman|junior year|senior year)\b"], text):
        return True
    # "class of 2028" / "c/o 2028" in a bio implies a future HS/college graduation -> likely a teen
    for m in re.finditer(r"\b(?:class of|c/?o)\s*(20\d{2})\b", text, flags=re.IGNORECASE):
        grad_year = int(m.group(1))
        if grad_year >= 2026:   # still in school as of the prototype's "now"
            return True
    for m in re.finditer(r"\bi'?m (\d{1,2})\b", text, flags=re.IGNORECASE):
        age = int(m.group(1))
        if age < 18:
            return True
    # "too young at 16", "just turned 16" — require an age context word (young/turned)
    # nearby so "at 14 weeks" / "only 15 minutes" don't false-trigger.
    for m in re.finditer(r"\b(?:young (?:at|enough at)?|just turned|turning)\s+(\d{1,2})\b",
                         text, flags=re.IGNORECASE):
        age = int(m.group(1))
        if 10 <= age < 18:
            return True
    for m in re.finditer(r"\b(\d{1,2}) ?(yo|y/o|years? old)\b", text, flags=re.IGNORECASE):
        age = int(m.group(1))
        if age < 18:
            return True
    return False


def should_engage(post):
    """
    Gate 1 — should we engage with this POST at all?

    Returns a dict:
      status: "block" | "flag" | "ok"
      reasons: list of human-readable reasons
      category: dominant category for the UI badge
    A 'block' means no comment is drafted. A 'flag' means a comment may be drafted
    but the human must look closely. 'ok' means safe to draft.
    """
    text = post.get("text", "") + " " + post.get("context", "")
    reasons, status, category = [], "ok", "safe"

    if _any(CRISIS_PATTERNS, text):
        return {"status": "block", "category": "crisis",
                "reasons": ["Possible crisis / suicidal ideation. " + CRISIS_RESOURCE_NOTE]}

    if _looks_like_minor(text):
        return {"status": "block", "category": "minor",
                "reasons": ["Author appears to be a minor. Do not engage as a brand."]}

    if _any(INAPPROPRIATE_INTERVENTION_PATTERNS, text):
        return {"status": "block", "category": "acute_situation",
                "reasons": ["Acute safety/abuse situation. Not appropriate for growth engagement."]}

    if _any(PRIVACY_PATTERNS, text):
        return {"status": "block", "category": "privacy",
                "reasons": ["Post contains sensitive/identifying info. Too sensitive to engage publicly."]}

    if _any(MEDICAL_RISK_PATTERNS, text):
        return {"status": "block", "category": "medical_risk",
                "reasons": ["Post involves a medication/medical decision. We must not give medical "
                            "advice; route to a human who can gently suggest a professional."]}

    # Softer signal: ambiguous distress that isn't an explicit crisis but shouldn't be
    # auto-engaged casually. Flag (not block) so a human looks closely.
    if _any(AMBIGUOUS_DISTRESS_PATTERNS, text):
        status = "flag"; category = "ambiguous_distress"
        reasons.append("Ambiguous distress language — not an explicit crisis, but review with care "
                       "before engaging (could be venting or could be more serious).")

    if _any(OFFTOPIC_PATTERNS, text):
        status = "flag"; category = "offtopic"
        reasons.append("Looks off-topic / not mental-health related.")

    if _any(SPAM_PATTERNS, text):
        status = "flag"; category = "spam_source"
        reasons.append("Author looks like a spam/promo account.")

    if status == "ok":
        reasons.append("No safety flags detected.")
    return {"status": status, "category": category, "reasons": reasons}


def check_comment(comment):
    """
    Gate 2 — is this DRAFTED COMMENT safe to post?

    Even when a post is safe to engage, the generated comment itself must not
    make medical claims, diagnose, or read as spam. This catches bad LLM output.
    """
    reasons, status = [], "ok"

    med = _any(MEDICAL_CLAIM_PATTERNS, comment)
    if med:
        status = "unsafe"
        reasons.append("Comment contains diagnosis / cure / treatment / prevention language.")

    spam = _any(SPAM_PATTERNS, comment)
    if spam:
        status = "unsafe"
        reasons.append("Comment reads as spammy / manipulative (CTA, links, urgency).")

    # Soft checks: encourage transparency + brevity
    mentions_sonia = bool(re.search(r"\bsonia\b", comment, flags=re.IGNORECASE))
    discloses = bool(re.search(r"\b(i (work|help) (with|at) sonia|full disclosure|i'?m (with|from) sonia)\b",
                               comment, flags=re.IGNORECASE))
    if mentions_sonia and not discloses:
        status = "unsafe" if status == "unsafe" else "flag"
        reasons.append("Mentions Sonia without a transparency disclosure.")

    if len(comment) > 400:
        status = "flag" if status == "ok" else status
        reasons.append("Comment is long for a social reply (>400 chars).")

    if status == "ok":
        reasons.append("Comment passed all content checks.")
    return {"status": status, "reasons": reasons,
            "mentions_sonia": mentions_sonia, "discloses": discloses}