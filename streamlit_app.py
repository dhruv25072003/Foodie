# streamlit_app.py
import os
import time
from typing import Optional, List, Dict, Any

import streamlit as st
import requests
import pandas as pd

# -----------------------
# Configuration: API base resolution
# -----------------------
def get_api_base():
    # priority: st.secrets["API_BASE"] -> env var API_BASE/FOODIE_API_BASE -> fallback
    try:
        api = None
        if hasattr(st, "secrets") and isinstance(st.secrets, dict) and st.secrets.get("API_BASE"):
            api = st.secrets.get("API_BASE")
        if not api:
            api = os.getenv("API_BASE") or os.getenv("FOODIE_API_BASE")
        if not api:
            api = "http://localhost:8000"
        if api.endswith("/"):
            api = api[:-1]
        return api
    except Exception:
        return "http://localhost:8000"

API_BASE = get_api_base()

# -----------------------
# Page config
# -----------------------
st.set_page_config(page_title="FoodieBot — Demo (Full)", layout="wide")
st.title("🍔 FoodieBot — Demo (Full)")

# -----------------------
# Session state initialization
# -----------------------
if "history" not in st.session_state:
    st.session_state.history: List[Dict[str, Any]] = []  # list of dicts {who, text, score, debug, ts}
if "session_id" not in st.session_state:
    st.session_state.session_id: Optional[str] = None
if "cart" not in st.session_state:
    st.session_state.cart: List[str] = []
if "suggested_products" not in st.session_state:
    st.session_state.suggested_products: List[Dict[str, Any]] = []

# -----------------------
# Small helpers for API
# -----------------------
def api_post(path: str, json_payload: dict = None, timeout: int = 10):
    url = f"{API_BASE}{path}"
    try:
        r = requests.post(url, json=json_payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API POST error {url}: {e}")
        return None

def api_get(path: str, params: dict = None, timeout: int = 10):
    url = f"{API_BASE}{path}"
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API GET error {url}: {e}")
        return None

def api_delete(path: str, timeout: int = 10):
    url = f"{API_BASE}{path}"
    try:
        r = requests.delete(url, timeout=timeout)
        r.raise_for_status()
        return r.json() if r.text else {"status":"deleted"}
    except requests.exceptions.RequestException as e:
        st.error(f"API DELETE error {url}: {e}")
        return None

def show_product_card(item: Dict[str, Any], show_actions: bool = True):
    """
    Renders a product card with image, description, tags and action buttons.
    """
    name = item.get("name") or "Unnamed"
    price = float(item.get("price") or 0.0)
    desc = item.get("description") or ""
    pid = item.get("product_id") or item.get("id") or ""
    spice = item.get("spice_level")
    mood_tags = item.get("mood_tags") or []
    dietary = item.get("dietary_tags") or []
    img = item.get("image_url") or item.get("image") or f"https://picsum.photos/seed/{pid}/320/200"

    cols = st.columns([1, 2])
    with cols[0]:
        try:
            st.image(img, use_column_width=True)
        except Exception:
            st.write("No image")
    with cols[1]:
        st.markdown(f"### {name} — ${price:.2f}")
        if desc:
            st.write(desc)
        cat = item.get("category")
        if cat:
            st.write(f"**Category:** {cat}")
        if mood_tags:
            st.write("Mood:", ", ".join(map(str, mood_tags)))
        if dietary:
            st.write("Dietary:", ", ".join(map(str, dietary)))
        if spice is not None:
            st.write(f"Spice: {spice}/10")
        st.write(f"Popularity: {item.get('popularity_score','N/A')}")
        if show_actions:
            a1, a2, a3 = st.columns([1, 1, 1])
            with a1:
                if st.button("Add to cart", key=f"add_{pid}"):
                    st.session_state.cart.append(pid)
                    st.success(f"Added {name} to cart (demo).")
            with a2:
                if st.button("View details", key=f"view_{pid}"):
                    details = api_get(f"/product/{pid}")
                    if details:
                        st.json(details)
            with a3:
                if st.button("Recommend similar", key=f"sim_{pid}"):
                    res = api_get("/collab", params={"product_id": pid, "limit": 6})
                    if res and res.get("results"):
                        st.write("Similar recommendations:")
                        for r in res.get("results", []):
                            st.markdown(f"- **{r.get('name')}** — ${r.get('price')}")
    st.markdown("---")

# -----------------------
# Sidebar navigation (keeps your existing chat as default)
# -----------------------
page = st.sidebar.radio("Navigate", ["Chat (default)", "Recommendations", "Analytics", "Admin", "Docs"])

# -----------------------
# Main: keep your original chat UI but enhance it with session controls and debug display
# -----------------------
if page == "Chat (default)":
    left, right = st.columns([2, 1])
    with left:
        st.header("💬 Chat with FoodieBot")
        # Reuse your existing chat input exactly
        user_input = st.text_input("You:", key="chat_input")
        if st.button("Send", key="send_btn"):
            if user_input.strip():
                payload = {"message": user_input}
                if st.session_state.session_id:
                    payload["session_id"] = st.session_state.session_id
                try:
                    resp = requests.post(f"{API_BASE}/chat", json=payload, timeout=8)
                    resp.raise_for_status()
                    data = resp.json()
                    # store session id
                    st.session_state.session_id = data.get("session_id")
                    # append to history
                    st.session_state.history.append({"who":"You","text":user_input,"score":None,"debug":None,"ts":time.time()})
                    st.session_state.history.append({
                        "who":"Bot",
                        "text": data.get("reply",""),
                        "score": data.get("interest_score"),
                        "debug": data.get("debug",""),
                        "ts":time.time()
                    })
                    # if suggested product ids included, fetch product details
                    suggested_ids = data.get("suggested") or []
                    if suggested_ids:
                        st.session_state.suggested_products = []
                        for pid in suggested_ids:
                            p = api_get(f"/product/{pid}")
                            if p:
                                st.session_state.suggested_products.append(p)
                except Exception as e:
                    st.error(f"API error: {e}")

        # Render history (newest first)
        if st.session_state.history:
            st.subheader("Conversation history")
            for msg in st.session_state.history[::-1]:
                if msg["who"] == "You":
                    st.markdown(f"**🧑 You:** {msg['text']}")
                else:
                    st.markdown(f"**🤖 Bot:** {msg['text']}")
                    if msg.get("score") is not None:
                        st.caption(f"Interest score: {msg.get('score')}")
                    if msg.get("debug"):
                        st.caption(f"Engine: {msg.get('debug')}")

        # Show suggested products if present
        if st.session_state.suggested_products:
            st.subheader("Suggested products")
            for p in st.session_state.suggested_products:
                show_product_card(p)

    # Right column: quick recommendations + session controls
    with right:
        st.header("⭐ Quick Recommendations & Session")
        # Quick mood/budget recs (keeps your original UI)
        mood = st.selectbox(
            "Mood",
            ["", "adventurous", "comfort", "indulgent", "healthy", "party", "refreshing", "cozy", "quick"],
        )
        budget = st.slider("Max price", 0.0, 30.0, 12.0, step=0.5)
        limit = st.number_input("How many results?", min_value=1, max_value=20, value=5, step=1)
        if st.button("Get Recommendations", key="recs_btn_right"):
            try:
                params = {"mood": mood or None, "budget": budget, "limit": limit}
                resp = requests.get(f"{API_BASE}/recommend", params=params, timeout=8)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    st.info("No recommendations found for that filter.")
                else:
                    for item in results:
                        show_product_card(item)
            except Exception as e:
                st.error(f"Recommendation API error: {e}")

        st.markdown("---")
        st.subheader("Session actions")
        st.write(f"Session id: {st.session_state.session_id or '— no session yet —'}")
        if st.button("Recommend from session"):
            if not st.session_state.session_id:
                st.warning("Start a conversation to create a session first.")
            else:
                res = api_get("/recommend_from_context", params={"session_id": st.session_state.session_id, "limit": 6})
                if res and res.get("results"):
                    st.success("Recommendations from session:")
                    for it in res.get("results", []):
                        show_product_card(it)
        if st.button("Clear session data"):
            st.session_state.session_id = None
            st.session_state.history = []
            st.session_state.suggested_products = []
            st.success("Session cleared.")
        st.markdown("---")
        st.subheader("Cart (demo)")
        if st.session_state.cart:
            for pid in st.session_state.cart:
                st.write(f"- {pid}")
            if st.button("Clear cart"):
                st.session_state.cart = []
                st.success("Cart cleared.")
        else:
            st.write("Cart empty")

# -----------------------
# Recommendations page (detailed)
# -----------------------
elif page == "Recommendations":
    st.header("🎯 Recommendations — filters & search")
    with st.form("rec_form"):
        mood = st.selectbox("Mood", ["", "adventurous", "comfort", "indulgent", "healthy", "party", "refreshing", "cozy", "quick"])
        budget = st.slider("Max price ($)", 0.0, 30.0, 12.0, step=0.5)
        limit = st.number_input("Results", min_value=1, max_value=30, value=8)
        submitted = st.form_submit_button("Get recommendations")
    if submitted:
        params = {"mood": mood or None, "budget": budget, "limit": limit}
        res = api_get("/recommend", params=params)
        if res:
            results = res.get("results", [])
            if not results:
                st.info("No recommendations for that filter.")
            else:
                for it in results:
                    show_product_card(it)

    st.markdown("---")
    st.subheader("Search products")
    q = st.text_input("Search term", key="rec_search")
    if st.button("Search products"):
        if not q.strip():
            st.warning("Enter a keyword.")
        else:
            out = api_get("/search", params={"q": q, "limit": 20})
            if out:
                for it in out.get("results", []):
                    show_product_card(it)

# -----------------------
# Analytics page
# -----------------------
elif page == "Analytics":
    st.header("📊 Analytics & Insights")
    st.subheader("Recent Conversations")
    conversations = api_get("/analytics/conversations", params={"limit": 500})
    if conversations:
        df = pd.DataFrame(conversations)
        if df.empty:
            st.info("No conversation logs yet.")
        else:
            # show key columns if present
            show_cols = [c for c in ["id","session_id","turn","user_message","bot_reply","interest_score","created_at"] if c in df.columns]
            st.dataframe(df[show_cols].sort_values(by="id", ascending=False).reset_index(drop=True), height=300)
            if "session_id" in df.columns:
                sel = st.selectbox("Pick session to visualize", [""] + df["session_id"].dropna().unique().tolist())
                if sel:
                    s_df = df[df["session_id"] == sel].sort_values("turn", ascending=True)
                    if "interest_score" in s_df.columns:
                        st.line_chart(s_df.set_index("turn")["interest_score"])
    st.markdown("---")
    st.subheader("Recent DB queries")
    queries = api_get("/analytics/recent_queries", params={"limit":300})
    if queries:
        qdf = pd.DataFrame(queries)
        if not qdf.empty:
            st.dataframe(qdf.sort_values("created_at", ascending=False).reset_index(drop=True), height=300)
        else:
            st.info("No queries logged yet.")
    st.markdown("---")
    st.subheader("Quick recommendation performance")
    if conversations:
        try:
            df2 = df.copy()
            if "interest_score" in df2.columns:
                df2["score_bin"] = pd.cut(df2["interest_score"].fillna(0), bins=[-1,20,40,60,80,100], labels=["0-20","21-40","41-60","61-80","81-100"])
                bin_counts = df2.groupby("score_bin").size()
                st.bar_chart(bin_counts)
        except Exception as e:
            st.warning(f"Could not compute quick metrics: {e}")

# -----------------------
# Admin page
# -----------------------
elif page == "Admin":
    st.header("⚙️ Admin — Products (CRUD)")
    st.subheader("Create / Add product")
    with st.form("add_prod"):
        name = st.text_input("Name")
        category = st.text_input("Category")
        price = st.number_input("Price ($)", min_value=0.0, value=9.99, step=0.5)
        desc = st.text_area("Description")
        mood_tags = st.text_input("Mood tags (comma separated)")
        dietary_tags = st.text_input("Dietary tags (comma separated)")
        image_url = st.text_input("Image URL (optional)")
        submitted = st.form_submit_button("Create product")
    if submitted:
        payload = {
            "name": name,
            "category": category,
            "price": float(price),
            "description": desc,
            "mood_tags": [t.strip() for t in mood_tags.split(",") if t.strip()],
            "dietary_tags": [t.strip() for t in dietary_tags.split(",") if t.strip()],
            "image_url": image_url or None
        }
        r = api_post("/admin/products", json_payload=payload)
        if r:
            st.success(f"Created product {r.get('product_id')}")

    st.markdown("---")
    st.subheader("Search & edit products")
    q = st.text_input("Search", key="admin_search")
    if st.button("Search products", key="admin_search_btn"):
        if not q.strip():
            st.warning("Type a search keyword.")
        else:
            out = api_get("/search", params={"q": q, "limit": 50})
            if out:
                for it in out.get("results", []):
                    st.markdown(f"**{it.get('name')}** — ${it.get('price')}")
                    st.write(it.get("description"))
                    colA, colB = st.columns([1,3])
                    with colA:
                        if st.button("Delete", key=f"del_{it.get('product_id')}"):
                            d = api_delete(f"/admin/products/{it.get('product_id')}")
                            if d:
                                st.success("Deleted.")
                    with colB:
                        if st.button("Edit", key=f"edit_{it.get('product_id')}"):
                            # inline editor form
                            with st.form(f"edit_form_{it.get('product_id')}"):
                                new_name = st.text_input("Name", value=it.get("name"))
                                new_cat = st.text_input("Category", value=it.get("category") or "")
                                new_price = st.number_input("Price", value=float(it.get("price") or 0.0))
                                new_desc = st.text_area("Description", value=it.get("description") or "")
                                submit_edit = st.form_submit_button("Save")
                                if submit_edit:
                                    payload = {
                                        "name": new_name,
                                        "category": new_cat,
                                        "price": float(new_price),
                                        "description": new_desc,
                                        "ingredients": it.get("ingredients") or [],
                                        "dietary_tags": it.get("dietary_tags") or [],
                                        "mood_tags": it.get("mood_tags") or [],
                                        "allergens": it.get("allergens") or [],
                                        "popularity_score": it.get("popularity_score", 50),
                                        "chef_special": it.get("chef_special", False),
                                        "limited_time": it.get("limited_time", False),
                                        "spice_level": it.get("spice_level", 0),
                                        "image_url": it.get("image_url")
                                    }
                                    upd = requests.put(f"{API_BASE}/admin/products/{it.get('product_id')}", json=payload)
                                    if upd.status_code == 200:
                                        st.success("Updated product.")
                                    else:
                                        st.error(f"Update failed: {upd.text}")
                    st.markdown("---")

# -----------------------
# Docs & quick tests
# -----------------------
elif page == "Docs":
    st.header("Docs & Quick Tests")
    st.markdown(f"**Backend API base:** `{API_BASE}`")
    st.markdown("""
    **Key endpoints**
    - POST /chat (body: {"message":"...", "session_id": optional})
    - GET /recommend?mood=...&budget=...&limit=...
    - GET /search?q=...&limit=...
    - GET /product/{product_id}
    - GET /analytics/conversations
    - GET /analytics/recent_queries
    - Admin: POST/PUT/DELETE /admin/products
    """)
    st.markdown("### Quick cURL example")
    st.code(f"""curl -X POST "{API_BASE}/chat" -H "Content-Type: application/json" -d '{{"message":"I want something spicy under $10"}}'""")
    st.write("End of docs.")

# -----------------------
# End of file
# -----------------------
