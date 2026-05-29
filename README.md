# sonia-comment-assist
Growth Engineering / Comment-Assist Prototype Take-Home

# Sonia · Comment-Assist (Prototype)

A small human-in-the-loop tool that helps Sonia's growth team find relevant public
posts, draft thoughtful comments, and **review every comment before anything is posted**.
The goal is *not* to spam — it's to participate in relevant conversations with comments
that are specific, kind, useful, and safe.

Because Sonia is a **mental-health** product, the safety layer is the centerpiece: the
tool refuses to engage with crisis posts, minors, and acute-emergency situations, and a
second gate blocks any drafted comment that diagnoses, claims to cure/treat, or reads as spam.

## Quick start (runs with no API key)

```bash
git clone <your-repo-url>
cd sonia-comment-assist

python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # defaults to AI_MODE=mock — no key needed
python app.py               # open http://127.0.0.1:5000
```

The app ships in **mock mode** so a reviewer can run it instantly. To use a real LLM,
set `AI_MODE=anthropic` and `ANTHROPIC_API_KEY` in `.env`. Behaviour (prompts, safety
rules) is identical; only draft quality changes.

## What a reviewer can do

- See 20 sourced posts ranked by a **relevance score**.
- See each post's **safety status** (safe / flagged / blocked) and *why*.
- See a **draft comment** plus a second **comment-level safety check**.
- **Approve**, **edit & save**, **reject**, or **mark unsafe** — saved to SQLite (`decisions.db`).
- **Export** all decisions as JSON (`/api/export`).

## Architecture

```
data/sample_posts.json
        │
        ▼
 safety.should_engage(post) ── block ──▶ no draft; reason shown to human
        │ ok / flag
        ▼
 ai_workflow.score_relevance(post)
        ▼
 ai_workflow.draft_comment(post) ──▶ safety.check_comment(draft) ──▶ reviewer UI
        │
        ▼
 db.save_decision()  → SQLite (decisions.db)
```

| File | Responsibility |
|------|----------------|
| `app.py` | Flask server, routes, wires the pipeline together |
| `safety.py` | **Two gates:** post-level engagement gate + comment-level content gate |
| `ai_workflow.py` | Relevance scoring + comment drafting (mock by default, Anthropic optional) |
| `db.py` | SQLite store for reviewer decisions (seeds 3 example decisions on first run) |
| `templates/index.html` + `static/style.css` | The review dashboard |
| `data/sample_posts.json` | 20 synthetic posts (see below) |

### Safety: what gets blocked vs flagged

- **Blocked (no comment drafted):** crisis / suicidal ideation, minors, acute
  emergencies (abuse in progress, ER/psych ward), privacy-sensitive posts (addresses, SSN).
- **Flagged (drafted but needs care):** off-topic posts, spam/promo source accounts.
- **Comment gate marks a draft `unsafe`** if it diagnoses, claims to cure/treat/prevent,
  reads as spam, or mentions Sonia without a transparency disclosure.

Try post **p09** ("do I have bipolar?") in the app — the post is engageable, but the draft
trips the comment gate (diagnosis + cure language), so it surfaces as **unsafe**. That
demonstrates both gates working independently.

## Demo data

`data/sample_posts.json` contains **20 synthetic posts** (`"is_real": false`). They are
mock — not scraped from real people — which avoids using anyone's private information while
still being realistic. They deliberately span every safety category so the gates are
visible: support-seeking, creators/partners, crisis, a minor, a diagnosis-bait post,
domestic-violence/privacy, grief, off-topic crypto, and a spam account.

## Tradeoffs & known limitations

- **Mock AI by default.** Drafts are template-based unless `AI_MODE=anthropic`. Real LLM
  output is more specific. The safety gates run the same regardless.
- **No live scraping.** This intentionally does **not** call the Instagram/X/Reddit APIs.
  Sourcing is mocked so the prototype can't get the team rate-limited or banned. Real
  sourcing would use official APIs / approved partners (see "next").
- **Keyword-based safety.** Transparent and auditable, but it can miss paraphrased crisis
  language. Production should add an LLM safety classifier as a third layer.
- **Single reviewer, local DB.** No auth, no multi-user, no audit of *who* decided.
- **Relevance is heuristic** in mock mode (keyword signals), not a trained ranker.

## What I'd build next

- Real sourcing via official APIs + an allow-list of communities/partners.
- LLM safety classifier layered on top of the keyword rules; log every block for review.
- Reviewer accounts + audit trail; per-platform comment-length/style rules.
- A/B feedback loop: which approved comments actually landed well, fed back into ranking.

## Endpoints

- `GET /` — dashboard
- `GET /api/posts` — all posts with relevance, safety, and draft
- `POST /api/decision` — `{post_id, status, final_comment, reviewer_note}`
- `GET /api/export` — all decisions as JSON
