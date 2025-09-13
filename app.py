# app.py
import os
from dotenv import load_dotenv
load_dotenv()

import logging
import sqlite3
import json
import uuid
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# local modules (make sure these files exist in the project)
from convo import update_context_and_score, _init_context
from recommender import recommend_by_preferences, collaborative_recommend
from analytics import init_db, log_turn, fetch_recent_queries, fetch_conversations
from convo_llm import parse_nlu_with_llm, generate_reply_with_llm

LOG = logging.getLogger("foodiebot")
logging.basicConfig(level=logging.INFO)

# DB path (can be overridden via .env)
DB = os.getenv("FOODIE_DB", "foodie_products.db")

app = FastAPI(title="FoodieBot API (Groq-enabled)")
init_db()

# in-memory session contexts
CONTEXTS: Dict[str, Dict[str, Any]] = {}

# -----------------------
# Utility / DB helpers
# -----------------------
def _connect():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------
# Request models
# -----------------------
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    product_id: Optional[str] = None

class ProductCreate(BaseModel):
    product_id: Optional[str] = None
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    ingredients: Optional[List[str]] = None
    price: float = 0.0
    calories: Optional[int] = None
    prep_time: Optional[str] = None
    dietary_tags: Optional[List[str]] = None
    mood_tags: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    popularity_score: Optional[int] = 50
    chef_special: Optional[bool] = False
    limited_time: Optional[bool] = False
    spice_level: Optional[int] = 0
    image_url: Optional[str] = None
    image_prompt: Optional[str] = None

# -----------------------
# Root / health
# -----------------------
@app.get("/")
def root():
    return {"status": "ok", "message": "FoodieBot API running. See /docs for endpoints."}

# -----------------------
# Chat endpoint (robust)
# -----------------------
@app.post("/chat")
def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    context = CONTEXTS.get(sid) or _init_context(sid)
    CONTEXTS[sid] = context

    # 1) NLU parse (Groq or fallback) - protect with try/except
    try:
        nlu_slots = parse_nlu_with_llm(req.message)
    except Exception as e:
        LOG.warning("NLU parse failed: %s", e)
        # minimal fallback
        nlu_slots = {"free_text": req.message}

    # 2) update context & score
    try:
        context, delta, total_score, _ = update_context_and_score(context, req.message)
        CONTEXTS[sid] = context
    except Exception as e:
        LOG.warning("Context update failed: %s", e)
        delta, total_score = 0, context.get("accumulated_score", 0)

    # 3) fetch candidate products (recommendation)
    products: List[Dict[str, Any]] = []
    try:
        products = recommend_by_preferences(
            mood=nlu_slots.get("mood") if isinstance(nlu_slots, dict) else None,
            budget=nlu_slots.get("budget") if isinstance(nlu_slots, dict) else None,
            dietary=nlu_slots.get("dietary") if isinstance(nlu_slots, dict) else None,
            nutrient=nlu_slots.get("nutrient") if isinstance(nlu_slots, dict) else None,
            limit=6
        )
    except Exception as e:
        LOG.warning("Recommend fetch failed: %s", e)
        products = []

    # 4) attempt to generate a reply via Groq wrapper (with fallback protected)
    try:
        reply_obj = generate_reply_with_llm(context, req.message, products[:4], total_score)
    except Exception as e:
        LOG.warning("Reply generation failed: %s", e)
        # safe fallback reply
        if products:
            p = products[0]
            reply_obj = {"reply": f"I found {p.get('name')} for ${float(p.get('price') or 0):.2f}. Want details?", "suggested":[p.get("product_id")], "mention_spice": bool(p.get("spice_level")), "debug":"fallback"}
        else:
            reply_obj = {"reply":"Tell me more about your mood, budget, or dietary needs.", "suggested": [], "mention_spice": False, "debug":"fallback_none"}

    # 5) log the turn (analytics) - non-blocking
    try:
        turn_num = len([h for h in context.get("history", []) if h.get("role") == "user"])
        log_turn(
            session_id=sid,
            turn=turn_num,
            user_message=req.message,
            bot_reply=reply_obj.get("reply"),
            score=total_score,
            intents=context.get("intents", {}),
            recommended=[p.get("product_id") for p in products[:6]],
            chosen=None
        )
    except Exception as e:
        LOG.warning("Analytics log failed: %s", e)

    return {
        "session_id": sid,
        "reply": reply_obj.get("reply"),
        "interest_score": total_score,
        "score_delta": delta,
        "nlu_slots": nlu_slots,
        "suggested": reply_obj.get("suggested", []),
        "debug": reply_obj.get("debug", "")
    }

# -----------------------
# Recommend from context
# -----------------------
@app.get("/recommend_from_context")
def recommend_from_context(session_id: str, limit: int = 6):
    context = CONTEXTS.get(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    intents = context.get("intents", {})
    try:
        recs = recommend_by_preferences(
            mood=intents.get("mood"),
            budget=intents.get("budget"),
            dietary=intents.get("dietary") if isinstance(intents.get("dietary"), list) else None,
            nutrient=intents.get("nutrient"),
            limit=limit
        )
    except Exception as e:
        LOG.warning("recommend_from_context failed: %s", e)
        recs = []
    # log system recommend
    try:
        log_turn(
            session_id=session_id,
            turn=len([h for h in context.get("history", []) if h.get("role") == "user"]),
            user_message="[SYSTEM] recommend_from_context",
            bot_reply=f"{len(recs)} recommended",
            score=context.get("accumulated_score"),
            intents=intents,
            recommended=[r.get("product_id") for r in recs],
            chosen=None
        )
    except Exception as e:
        LOG.warning("Analytics log failed for recommend_from_context: %s", e)
    return {"session_id": session_id, "results": recs, "intents": intents}

# -----------------------
# Product detail
# -----------------------
@app.get("/product/{product_id}")
def get_product(product_id: str):
    conn = _connect(); cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE product_id=?", (product_id,))
    r = cur.fetchone(); conn.close()
    if not r:
        raise HTTPException(status_code=404, detail="Product not found")
    item = dict(r)
    for f in ("ingredients","dietary_tags","mood_tags","allergens"):
        if item.get(f):
            try:
                item[f] = json.loads(item[f])
            except Exception:
                pass
    return item

# -----------------------
# Simple recommend endpoint
# -----------------------
@app.get("/recommend")
def recommend(mood: Optional[str] = None, budget: Optional[float] = None, limit: int = 6):
    try:
        recs = recommend_by_preferences(mood=mood, budget=budget, limit=limit)
    except Exception as e:
        LOG.warning("Recommend endpoint failed: %s", e)
        recs = []
    return {"results": recs}

# -----------------------
# Search (name/description)
# -----------------------
@app.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = 10):
    conn = _connect(); cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE name LIKE ? OR description LIKE ? LIMIT ?", (f"%{q}%", f"%{q}%", limit))
    rows = [dict(r) for r in cur.fetchall()]; conn.close()
    for r in rows:
        for f in ("ingredients","dietary_tags","mood_tags","allergens"):
            if r.get(f):
                try: r[f] = json.loads(r[f])
                except: pass
    return {"count": len(rows), "results": rows}

# -----------------------
# Analytics endpoints
# -----------------------
@app.get("/analytics/conversations")
def api_fetch_conversations(limit: int = 50):
    try:
        rows = fetch_conversations(limit=limit)
        return rows
    except Exception as e:
        LOG.exception("Failed fetching conversations: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {e}")

@app.get("/analytics/recent_queries")
def api_recent_queries(limit: int = 50):
    try:
        rows = fetch_recent_queries(limit=limit)
        return rows
    except Exception as e:
        LOG.exception("Failed fetching queries: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch queries: {e}")

# -----------------------
# Admin CRUD (create / update / delete)
# -----------------------
def _db_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.post("/admin/products", tags=["admin"])
def admin_create_product(payload: ProductCreate):
    pid = payload.product_id or f"P{int(time.time()*1000) % 1000000}"
    conn = _db_conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (
            product_id, name, category, description, ingredients, price, calories, prep_time,
            dietary_tags, mood_tags, allergens, popularity_score, chef_special, limited_time,
            spice_level, image_url, image_prompt, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pid,
        payload.name,
        payload.category,
        payload.description,
        json.dumps(payload.ingredients or []),
        float(payload.price),
        int(payload.calories) if payload.calories is not None else None,
        payload.prep_time,
        json.dumps(payload.dietary_tags or []),
        json.dumps(payload.mood_tags or []),
        json.dumps(payload.allergens or []),
        int(payload.popularity_score or 50),
        1 if payload.chef_special else 0,
        1 if payload.limited_time else 0,
        int(payload.spice_level or 0),
        payload.image_url,
        payload.image_prompt,
        datetime.utcnow().isoformat()
    ))
    conn.commit(); conn.close()
    return {"status": "created", "product_id": pid}

@app.put("/admin/products/{product_id}", tags=["admin"])
def admin_update_product(product_id: str, payload: ProductCreate):
    conn = _db_conn(); cur = conn.cursor()
    cur.execute("SELECT product_id FROM products WHERE product_id=?", (product_id,))
    if not cur.fetchone():
        conn.close(); raise HTTPException(status_code=404, detail="Product not found")
    cur.execute("""
        UPDATE products SET
            name=?, category=?, description=?, ingredients=?, price=?, calories=?, prep_time=?,
            dietary_tags=?, mood_tags=?, allergens=?, popularity_score=?, chef_special=?, limited_time=?,
            spice_level=?, image_url=?, image_prompt=?
        WHERE product_id=?
    """, (
        payload.name,
        payload.category,
        payload.description,
        json.dumps(payload.ingredients or []),
        float(payload.price),
        int(payload.calories) if payload.calories is not None else None,
        payload.prep_time,
        json.dumps(payload.dietary_tags or []),
        json.dumps(payload.mood_tags or []),
        json.dumps(payload.allergens or []),
        int(payload.popularity_score or 50),
        1 if payload.chef_special else 0,
        1 if payload.limited_time else 0,
        int(payload.spice_level or 0),
        payload.image_url,
        payload.image_prompt,
        product_id
    ))
    conn.commit(); conn.close()
    return {"status": "updated", "product_id": product_id}

@app.delete("/admin/products/{product_id}", tags=["admin"])
def admin_delete_product(product_id: str):
    conn = _db_conn(); cur = conn.cursor()
    cur.execute("SELECT product_id FROM products WHERE product_id=?", (product_id,))
    if not cur.fetchone():
        conn.close(); raise HTTPException(status_code=404, detail="Product not found")
    cur.execute("DELETE FROM products WHERE product_id=?", (product_id,))
    conn.commit(); conn.close()
    return {"status": "deleted", "product_id": product_id}

# -----------------------
# Collaborative recommend endpoint
# -----------------------
@app.get("/collab")
def collab(product_id: str, limit: int = 5):
    try:
        recs = collaborative_recommend(product_id, limit=limit)
    except Exception as e:
        LOG.warning("Collaborative recommend failed: %s", e)
        recs = []
    return {"results": recs}

# -----------------------
# Debug: show in-memory sessions
# -----------------------
@app.get("/debug/sessions")
def debug_sessions():
    out = {}
    for sid, ctx in CONTEXTS.items():
        out[sid] = {"intents": ctx.get("intents"), "accumulated_score": ctx.get("accumulated_score"), "history_len": len(ctx.get("history", []))}
    return out
