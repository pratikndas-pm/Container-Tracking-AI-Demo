# FastAPI backend for Vercel – Container Tracking Demo
# (see previous message for detailed comments)
import os, re, math, json, datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, Body
from fastapi.responses import JSONResponse
import httpx

APP_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_SHIPS = os.path.join(APP_DIR, "data", "ships.json")
DATA_ETA   = os.path.join(APP_DIR, "data", "eta_model.json")
DATA_RISK  = os.path.join(APP_DIR, "data", "region_risk.json")
app = FastAPI(title="Container Tracking Demo")

R_EARTH_KM = 6371.0
KM_PER_NM  = 1.852
def to_rad(d: float): return d*math.pi/180.0
def haversine_km(a_lat, a_lon, b_lat, b_lon):
    d_lat = to_rad(b_lat - a_lat); d_lon = to_rad(b_lon - a_lon)
    lat1 = to_rad(a_lat); lat2 = to_rad(b_lat)
    h = math.sin(d_lat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(d_lon/2)**2
    return 2*R_EARTH_KM*math.asin(math.sqrt(h))
def load_json(p): 
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

async def open_meteo(lat: float, lon: float):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, params=params); r.raise_for_status(); return r.json()

def ml_eta(distance_nm: float, speed_kts: float, wind_mps: float, congestion_idx: float):
    m = load_json(DATA_ETA); inv = 1.0/max(speed_kts,0.1)
    hours = float(m["intercept"]) + float(m["coef"]["distance_nm"])*distance_nm + float(m["coef"]["inv_speed"])*inv + float(m["coef"]["wind"])*wind_mps + float(m["coef"]["congestion"])*congestion_idx
    sigma = float(m.get("sigma_hours", 2.5))
    return {"hours": float(hours), "ci_90": [float(hours-1.64*sigma), float(hours+1.64*sigma)]}

def risk_band(pred_hours, planned_hours, wind_mps, region: str):
    base = float(load_json(DATA_RISK).get(region, 0.25))
    drift = max(pred_hours - planned_hours, 0.0)/max(planned_hours,1.0)
    weather = min(wind_mps/15.0, 1.0)
    score = min(1.0, 0.5*drift + 0.3*weather + 0.2*base)
    band = "LOW"
    if score >= 0.66: band = "HIGH"
    elif score >= 0.33: band = "MED"
    return {"score": score, "band": band}

def enrich(it: Dict[str, Any]) -> Dict[str, Any]:
    dist_nm = haversine_km(it["lat"], it["lon"], it["waypoint"]["lat"], it["waypoint"]["lon"]) / KM_PER_NM
    wind = 5.0
    pred = ml_eta(dist_nm, it["speedKts"], wind, 0.25)
    eta  = (datetime.datetime.utcnow() + datetime.timedelta(hours=pred["hours"])).isoformat(timespec="minutes") + "Z"
    r    = risk_band(pred["hours"], it["etaPlannedHrs"], wind, it.get("region", "Indian Ocean"))
    out  = it.copy()
    out["metrics"] = {"distNm":dist_nm,"predHours":pred["hours"],"etaUtc":eta,"ci90":pred["ci_90"],"onTime":pred["hours"] <= it["etaPlannedHrs"]*1.1,"risk":r["band"],"riskScore":r["score"]}
    return out
def load_items_enriched(): return [enrich(x) for x in load_json(DATA_SHIPS)]

def canon(s: str): return re.sub(r"[^A-Z0-9]","",str(s).upper())
def key10(s: str): 
    c = canon(s); return c[:10] if len(c)>=10 else c
def item_summary(it: Dict[str, Any]) -> str:
    m = it["metrics"]; ontxt = "on-time" if m["onTime"] else "delayed"
    frm = it.get("origin","Current"); to = it.get("destination","next waypoint")
    return f"{it['vessel']} — {it['id']} ({frm} → {to}): {ontxt}. ETA {m['etaUtc']}, predicted {m['predHours']:.1f}h (±{abs(m['ci90'][1]-m['predHours']):.1f}h @90%). Risk {m['risk']} (score {m['riskScore']:.2f}). Distance ~{m['distNm']:.0f} nm at {it['speedKts']:.1f} kts."

app = FastAPI()

@app.get('/api/health')
def health(): return {"ok": True}

@app.get('/api/ships')
def ships(): return {"items": load_items_enriched()}

@app.get('/api/container')
def api_container(cn: str = Query(...)):
    q_raw = cn.strip(); q = canon(q_raw); q10 = key10(q_raw)
    items = load_items_enriched()
    for s in items:
        if q.lower() in s["id"].lower() or any(q in canon(c) for c in s["containers"]):
            return {"item": s, "summary": item_summary(s), "matchedBy": "exact"}
    exact10 = []
    for s in items:
        for c in s["containers"]:
            if key10(c)==q10 and len(q10)==10: exact10.append(s); break
    if exact10:
        primary = exact10[0]
        alts = list({c for s in exact10 for c in s["containers"] if key10(c)==q10})[:10]
        return {"item": primary, "summary": item_summary(primary), "matchedBy": "key10", "alternates": alts}
    suggestions=[]
    if len(q)>=4:
        for s in items:
            if q in canon(s["id"]) or any(canon(c).startswith(q) for c in s["containers"]):
                suggestions.append({"id":s["id"],"vessel":s["vessel"],"sample":s["containers"][0]})
        seen=set(); uniq=[]
        for r in suggestions:
            if r["id"] not in seen: seen.add(r["id"]); uniq.append(r)
            if len(uniq)>=10: break
        if uniq: return JSONResponse({"error":"No exact match. Suggestions:", "suggestions": uniq}, status_code=404)
    return JSONResponse({"error":"Not found"}, status_code=404)

@app.get('/api/weather')
async def weather(lat: float, lon: float):
    try: return await open_meteo(lat, lon)
    except httpx.HTTPError as e: return JSONResponse({"error": str(e)}, status_code=502)

@app.post('/api/summary')
def summary(cn: Optional[str] = Query(None), q: Optional[str] = Query(None)):
    items = load_items_enriched()
    if not cn: return {"summary": "Please provide ?cn=<container> for a per-container summary."}
    qcanon = canon(cn); q10=key10(cn)
    for s in items:
        if qcanon.lower() in s["id"].lower() or any(qcanon in canon(c) for c in s["containers"]):
            return {"summary": item_summary(s)}
    for s in items:
        if any(key10(c)==q10 and len(q10)==10 for c in s["containers"]): return {"summary": item_summary(s)}
    return {"summary": "No shipment matched that container."}
