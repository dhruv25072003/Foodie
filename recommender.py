# recommender.py (sqlite sync)
import sqlite3, json, time, os
DB = os.getenv('FOODIE_DB','foodie_products.db')
def _connect():
    conn = sqlite3.connect(DB, check_same_thread=False); conn.row_factory = sqlite3.Row; return conn
def _parse_row(r):
    d = dict(r)
    for f in ('ingredients','dietary_tags','mood_tags','allergens'):
        if d.get(f) and isinstance(d[f], str):
            try: d[f]=json.loads(d[f])
            except: pass
    return d
def fetch_products(where='1=1', params=(), limit=50):
    sql = f"SELECT * FROM products WHERE {where} LIMIT ?"
    start=time.time(); conn=_connect(); cur=conn.cursor(); cur.execute(sql, params + (limit,)); rows=[_parse_row(r) for r in cur.fetchall()]; conn.close()
    return rows
def recommend_by_preferences(mood=None, budget=None, dietary=None, nutrient=None, limit=10):
    clauses=[]; params=[]
    if mood: clauses.append('mood_tags LIKE ?'); params.append(f"%{mood}%")
    if budget is not None: clauses.append('price <= ?'); params.append(float(budget))
    if dietary:
        for d in dietary: clauses.append('dietary_tags LIKE ?'); params.append(f"%{d}%")
    if nutrient:
        if nutrient=='protein': clauses.append('calories >= ?'); params.append(300)
        elif nutrient=='low_carb': clauses.append('calories <= ?'); params.append(400)
        elif nutrient=='low_calorie': clauses.append('calories <= ?'); params.append(250)
    where = ' AND '.join(clauses) if clauses else '1=1'
    rows = fetch_products(where, tuple(params), limit=200)
    def score(item):
        s = float(item.get('popularity_score',50))
        if mood:
            tags = item.get('mood_tags') or []
            if isinstance(tags, list) and mood in tags: s+=25
        if dietary:
            tags = item.get('dietary_tags') or []; match=0
            if isinstance(tags,list):
                for d in dietary:
                    if d in tags: match+=1
            s += 12*match
        if nutrient=='protein' and item.get('calories',0)>=300: s+=10
        s -= float(item.get('price',0))*0.2
        return s
    rows_sorted = sorted(rows, key=score, reverse=True)
    return rows_sorted[:limit]
def collaborative_recommend(product_id, limit=5):
    conn=_connect(); cur=conn.cursor(); cur.execute('SELECT category FROM products WHERE product_id=?',(product_id,)); r=cur.fetchone()
    if not r: conn.close(); return []
    category=r['category']; cur.execute('SELECT * FROM products WHERE category=? AND product_id<>? ORDER BY popularity_score DESC LIMIT ?',(category,product_id,limit))
    rows=[_parse_row(rr) for rr in cur.fetchall()]; conn.close(); return rows
