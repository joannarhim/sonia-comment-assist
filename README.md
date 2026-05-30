# Sonia Health: Comment-Assist Prototype

Comment assist prototype that helps Sonia's growth team find relevant public
posts, draft thoughtful comments, and **review every comment before anything is posted**.
The goal is to *participate* in relevant conversations with comments that are specific, kind, useful, and safe.

Since Sonia is a **mental-health** AI companion, the safety layer is the important part! The
tool refuses to engage with crisis posts, minors, and acute-emergency situations, and it
blocks any drafted comment that diagnoses, claims to cure/treat, or reads as spam.

## Set Up (runs with no API key)

```bash
git clone https://github.com/joannarhim/sonia-comment-assist.git 
cd sonia-comment-assist

python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # defaults to AI_MODE=mock — no key needed
python app.py               #open http://127.0.0.1:5000
```

Open the app at localhost URL: http://127.0.0.1:5000

## Set Up (runs with API key)

The app is currently in **mock mode** so a reviewer can run it instantly. To use a real LLM,
set `AI_MODE=anthropic` and `ANTHROPIC_API_KEY` in `.env`. Behaviour (prompts, safety
rules) is identical.

## What a reviewer can do

- See 42 sourced posts ranked by a **relevance score**.
- See each post's **safety status** (safe / flagged / blocked) and *why*.
- See a **draft comment** plus a second **comment-level safety check**.
- **Approve**, **edit & save**, **reject**, or **mark unsafe** — saved to SQLite (`decisions.db`).
- **Export** all decisions as JSON (`/api/export`).

## Architecture

```
 data/sample_posts.json
        │
        ▼
 safety.should_engage(post) ── block ──▶ no draft
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
| `data/sample_posts.json` | 42 synthetic posts (see below) |

## Demo data

`data/sample_posts.json` contains **42 synthetic posts** (`"is_real": false`). They are
mock and not scraped from real people, which avoids using anyone's private information while
still being realistic. They span across every safety category so the gates are
visible: support-seeking, creators/partners, crisis, a minor, a diagnosis-bait post,
domestic-violence/privacy, grief, off-topic crypto, and a spam account.
A few sample reviewer decisions are seeded automatically the first time you run the app, so the dashboard isn't empty.

### Safety: what gets blocked vs flagged

- **Blocked (no comment drafted):** crisis / suicidal ideation, minors, acute
  emergencies (abuse in progress, ER/psych ward), privacy-sensitive posts (addresses, SSN).
- **Flagged (drafted but needs care):** off-topic posts, spam/promo source accounts.
- **Comment gate marks a draft `unsafe`** if it diagnoses, claims to cure/treat/prevent,
  reads as spam, or mentions Sonia without a transparency disclosure.

### Tradeoffs & known limitations

- **Keyword-based safety is not perfect:** The gates use transparent keyword rules, so paraphrased crisis 
  slips through as safe. These are left in on purpose as the case for an LLM safety classifier in
  production. Broadening rules also raises false positives (caught "at 14 weeks pregnant"
  before tightening), which is inherent to keyword matching.
- **Mock AI by default:** Scoring and drafting run in deterministic mock mode (no API key needed)
  AI_MODE=anthropic uses a real LLM. Safety gates run identically in both.
- **Relevance score is a placeholder:** score is hand-tuned for ranking, not calibrated.
- **Single reviewer and local SQLite:** No authorization, multi-user, or per-platform comment rules.

## Endpoints

- `GET /` — dashboard
- `GET /api/posts` — all posts with relevance, safety, and draft
- `POST /api/decision` — `{post_id, status, final_comment, reviewer_note}`
- `GET /api/export` — all decisions as JSON
