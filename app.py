"""
app.py
======
Flask server that ties the pipeline together (shown in readme.md)

The reviewer can Approve / Edit / Reject / Mark unsafe. All decisions persist.
"""

import json
import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

import safety
import ai_workflow
import db

load_dotenv()

app = Flask(__name__)
DATA_PATH = os.path.join("data", "sample_posts.json")

# Simple in-memory cache so we don't re-run the AI workflow on every page load.
_analysis_cache = {}


def load_posts():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_post(post):
    """Run the full pipeline for one post and return everything the UI needs."""
    if post["id"] in _analysis_cache:
        return _analysis_cache[post["id"]]

    engage = safety.should_engage(post)
    relevance = ai_workflow.score_relevance(post)

    draft, comment_check = None, None
    if engage["status"] != "block":
        draft = ai_workflow.draft_comment(post)
        comment_check = safety.check_comment(draft)

    result = {
        "post": post,
        "engage": engage,            # post-level safety gate
        "relevance": relevance,      # {score, reason}
        "draft": draft,              # drafted comment (or None if blocked)
        "comment_check": comment_check,  # comment-level safety gate (or None)
    }
    _analysis_cache[post["id"]] = result
    return result


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/posts")
def api_posts():
    posts = load_posts()
    analyzed = [analyze_post(p) for p in posts]
    # Sort: highest relevance first, but push blocked posts to a clearly separate group.
    analyzed.sort(key=lambda a: (a["engage"]["status"] == "block",
                                 -a["relevance"]["score"]))
    decisions = db.get_decisions()
    for a in analyzed:
        a["decision"] = decisions.get(a["post"]["id"])
    return jsonify(analyzed)


@app.route("/api/decision", methods=["POST"])
def api_decision():
    data = request.get_json(force=True)
    pid = data.get("post_id")
    status = data.get("status")              # approved | rejected | unsafe | edited
    final_comment = data.get("final_comment")
    note = data.get("reviewer_note")
    if not pid or status not in {"approved", "rejected", "unsafe", "edited"}:
        return jsonify({"error": "invalid payload"}), 400
    db.save_decision(pid, status, final_comment, note)
    return jsonify({"ok": True, "decision": db.get_decisions().get(pid)})


@app.route("/api/export")
def api_export():
    return app.response_class(db.export_decisions_json(), mimetype="application/json")


if __name__ == "__main__":
    db.init_db(seed=True)
    print(f"\n  AI_MODE = {ai_workflow.AI_MODE}  (set AI_MODE=anthropic in .env for real LLM)")
    print("  Open http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
