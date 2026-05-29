# AI / Work Log

Short log of how this prototype was built and where AI was used.

## Approach
- Scoped to the rubric: a runnable web app + AI workflow + an explicit safety layer,
  deliberately **not** overbuilt (no live scraping, no auth, no infra).
- Identified that Sonia is a mental-health product, so I made the **safety filter the
  centerpiece** rather than a checkbox. Crisis/minor/acute/privacy posts are hard-blocked;
  a second gate blocks unsafe *comments* (diagnosis/cure/spam/undisclosed brand mention).

## Where AI was used
- Used an AI assistant to scaffold the Flask app, write the mock AI workflow, draft the
  20 synthetic sample posts, and write the safety rule sets and README.
- All safety categories, the two-gate design, and the "block vs flag vs draft" policy were
  my product decisions; AI implemented them.

## Build steps
1. Defined the pipeline: source → safety gate → relevance → draft → comment gate → review.
2. Wrote `safety.py` first (the hard part) with transparent, auditable keyword rules.
3. Built `ai_workflow.py` with a deterministic mock so it runs with no API key, plus an
   optional Anthropic path behind `AI_MODE`.
4. Built the Flask API + a clean review dashboard.
5. Smoke-tested the pipeline on all 20 posts and verified the endpoints + UI render.

## Verification
- Confirmed crisis (p07), minor (p08), and acute-abuse (p17) posts are blocked.
- Confirmed the diagnosis-bait post (p09) drafts a comment that the comment gate flags
  as **unsafe** — proving the two gates work independently.
- Confirmed Approve/Edit/Reject/Unsafe persist to SQLite and export as JSON.
