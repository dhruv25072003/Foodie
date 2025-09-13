# convo_llm.py
"""
FoodieBot Conversational Intelligence with Groq SDK.
- Uses Groq for NLU + reply generation (if GROQ_API_KEY is set).
- Strict JSON enforcement for Groq replies.
- Fallbacks ensure system never breaks.
"""

import os, json, re, logging
from typing import Dict, Any, List, Optional

try:
    from groq import Groq
except ImportError:
    Groq = None

LOG = logging.getLogger("convo_llm")
LOG.setLevel(logging.INFO)

# -------------------
# Config
# -------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY and Groq else None

# -------------------
# Prompts
# -------------------
NLU_PROMPT = """You are a strict JSON extractor.
Return ONLY valid JSON with keys: mood, budget, dietary, nutrient, spicy, question, order, enthusiasm, free_text

User message: "{message}"
"""

REPLY_PROMPT = """You are FoodieBot. Use ONLY the `products` list provided.
Never invent products or prices.
Always return ONLY valid JSON. Do not include extra text, comments, or markdown.

Inputs:
- context: {context}
- user_message: "{message}"
- products: {products}
- interest_score: {score}

Return ONLY valid JSON with keys:
- reply (string): a natural conversational response, must reference real product names
- suggested (list of product_id strings, 0–3)
- mention_spice (boolean)
- debug (string, short reason why you chose these products)
"""

# -------------------
# Helpers
# -------------------
def _extract_json(text: str) -> Optional[str]:
    if not text or "{" not in text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end+1]
    return None

def _clean_json_string(s: str) -> str:
    # fix trailing commas
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # strip weird unicode
    s = s.replace("\u00a0", " ")
    return s.strip()

def _safe_parse_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        LOG.warning("Raw JSON parse failed: %s", e)
        try:
            return json.loads(_clean_json_string(text))
        except Exception as e2:
            LOG.warning("Cleanup JSON parse failed: %s", e2)
            return {}

def _safe_json(obj):
    """Recursively convert sets to lists for JSON serialization."""
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(x) for x in obj]
    return obj

def _call_groq(prompt: str, max_tokens: int = 300, temperature: float = 0.0) -> str:
    if not client:
        raise RuntimeError("Groq not configured — set GROQ_API_KEY.")
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=max_tokens,
        temperature=temperature,
        top_p=1,
        stream=False
    )
    return resp.choices[0].message.content

# -------------------
# Public
# -------------------
def parse_nlu_with_llm(message: str) -> Dict[str, Any]:
    try:
        prompt = NLU_PROMPT.format(message=message.replace('"','\\"'))
        out = _call_groq(prompt, max_tokens=200, temperature=0.0)
        jtxt = _extract_json(out) or out
        parsed = _safe_parse_json(jtxt)
        return {
            "mood": parsed.get("mood"),
            "budget": _to_float(parsed.get("budget")),
            "dietary": parsed.get("dietary") or [],
            "nutrient": parsed.get("nutrient"),
            "spicy": bool(parsed.get("spicy")),
            "question": bool(parsed.get("question")),
            "order": bool(parsed.get("order")),
            "enthusiasm": bool(parsed.get("enthusiasm")),
            "free_text": parsed.get("free_text") or message
        }
    except Exception as e:
        LOG.warning("Groq NLU failed — fallback. Error: %s", e)
        return _fallback_nlu(message)

def generate_reply_with_llm(context: Dict[str,Any], user_message: str,
                            products: List[Dict[str,Any]], interest_score: int) -> Dict[str,Any]:
    safe_products = [
        {
            "product_id": p.get("product_id"),
            "name": p.get("name"),
            "price": p.get("price"),
            "spice_level": p.get("spice_level"),
            "popularity_score": p.get("popularity_score"),
        }
        for p in (products or [])[:4]
    ]
    try:
        prompt = REPLY_PROMPT.format(
            context=json.dumps(_safe_json(context)),
            message=user_message.replace('"','\\"'),
            products=json.dumps(_safe_json(safe_products)),
            score=interest_score
        )
        out = _call_groq(prompt, max_tokens=300, temperature=0.2)
        jtxt = _extract_json(out) or out

        parsed = _safe_parse_json(jtxt)
        if not parsed:  # if still broken, wrap text as reply
            return {
                "reply": out.strip(),
                "suggested": [],
                "mention_spice": False,
                "debug": "wrapped_text"
            }

        return {
            "reply": parsed.get("reply","").strip(),
            "suggested": parsed.get("suggested") or [],
            "mention_spice": bool(parsed.get("mention_spice", False)),
            "debug": parsed.get("debug","groq")
        }
    except Exception as e:
        LOG.warning("Groq reply failed — fallback. Error: %s", e)
        return _fallback_reply(context, user_message, safe_products, interest_score)

# -------------------
# Fallbacks
# -------------------
def _to_float(v):
    try:
        return float(v) if v is not None else None
    except:
        if isinstance(v, str):
            m = re.search(r"(\d+(\.\d+)?)", v)
            if m: return float(m.group(1))
    return None

def _fallback_nlu(message: str) -> Dict[str, Any]:
    txt = (message or "").lower()
    return {
        "mood": None,
        "budget": _to_float(re.search(r"\$(\d+)", txt).group(1)) if re.search(r"\$(\d+)", txt) else None,
        "dietary": ["vegetarian"] if "vegetarian" in txt else [],
        "nutrient": "protein" if "protein" in txt else None,
        "spicy": "spicy" in txt,
        "question": "?" in txt or "how" in txt,
        "order": any(w in txt for w in ["order","add","buy","take"]),
        "enthusiasm": any(w in txt for w in ["love","perfect","amazing"]),
        "free_text": message
    }

def _fallback_reply(context, user_message: str, products: List[Dict[str,Any]], interest_score: int) -> Dict[str,Any]:
    if products:
        best = products[0]
        return {
            "reply": f"I found {best['name']} for ${float(best['price'] or 0):.2f}. Want me to add it?",
            "suggested": [best.get("product_id")],
            "mention_spice": bool(best.get("spice_level")),
            "debug": "fallback"
        }
    return {"reply":"Tell me your food mood or budget!", "suggested": [], "mention_spice": False, "debug":"fallback_none"}
