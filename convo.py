# convo.py (simplified context + scoring)
import re, uuid
from typing import Optional
ENGAGEMENT_FACTORS = {'specific_preferences':15,'dietary_restrictions':10,'budget_mention':5,'mood_indication':20,'question_asking':10,'enthusiasm_words':8,'price_inquiry':25,'order_intent':30,'nutrient_preference':12}
NEGATIVE_FACTORS = {'hesitation':-10,'budget_concern':-15,'dietary_conflict':-20,'rejection':-25,'delay_response':-5}
DIETARY_KEYWORDS = ["vegan","vegetarian","gluten_free","dairy_free","nut_free"]

def _extract_budget(txt):
    import re
    m = re.search(r"under\s*\$?\s*(\d+(?:\.\d+)?)", txt)
    if m: return float(m.group(1))
    m2 = re.search(r"\$\s*(\d+(?:\.\d+)?)", txt)
    if m2: return float(m2.group(1))
    return None

def simple_nlu(text: str) -> dict:
    txt = (text or "").lower()
    out = {}
    b = _extract_budget(txt)
    if b: out['budget']=b
    for d in DIETARY_KEYWORDS:
        if d in txt: out.setdefault('dietary',[]).append(d)
    if any(w in txt for w in ["spicy","hot","chili","jalape"]): out['spicy']=True
    if any(w in txt for w in ["order","add to cart","i'll take","i will take","buy"]): out['order']=True
    if any(w in txt for w in ["love","perfect","amazing","delicious"]): out['enthusiasm']=True
    if '?' in txt: out['question']=True
    for mood in ["adventurous","comfort","healthy","indulgent","quick","refreshing","cozy","party"]:
        if mood in txt: out['mood']=mood; break
    return out

def _init_context(session_id: Optional[str]=None):
    if session_id is None: session_id=str(uuid.uuid4())
    return {'session_id':session_id,'history':[],'intents':{},'accumulated_score':0,'seen_intents':set()}

def update_context_and_score(context, text, product_tags=None):
    if context is None: context=_init_context()
    nlu = simple_nlu(text)
    score_delta = 0
    if 'mood' in nlu: score_delta += ENGAGEMENT_FACTORS['mood_indication']
    if 'dietary' in nlu: score_delta += ENGAGEMENT_FACTORS['dietary_restrictions']*len(nlu.get('dietary',[]))
    if 'budget' in nlu: score_delta += ENGAGEMENT_FACTORS['budget_mention']
    if 'question' in nlu: score_delta += ENGAGEMENT_FACTORS['question_asking']
    if 'enthusiasm' in nlu: score_delta += ENGAGEMENT_FACTORS['enthusiasm_words']
    if 'order' in nlu: score_delta += ENGAGEMENT_FACTORS['order_intent']
    if 'spicy' in nlu: score_delta += ENGAGEMENT_FACTORS['specific_preferences']
    context['history'].append({'role':'user','text':text,'nlu':nlu,'score_delta':score_delta})
    context['accumulated_score'] = max(0,min(100, context.get('accumulated_score',0) + score_delta))
    return context, score_delta, context['accumulated_score'], nlu

def build_reply(context, nlu):
    if nlu.get('order'): return "Sure — I can add that to your cart."
    if nlu.get('mood'): return f"Searching for {nlu.get('mood')} options."
    if nlu.get('nutrient'): return f"Looking for {nlu.get('nutrient')} options."
    if nlu.get('spicy'): return "You like spicy! Want spicy under a budget?"
    return "Tell me more about your preferences (mood, budget, dietary)."
