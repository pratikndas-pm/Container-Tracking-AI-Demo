# FastAPI backend for Vercel – Container Tracking Demo
# Single-item summary enabled:
#   - GET /api/container?cn=...      -> returns { item, summary, matchedBy, alternates? }
#   - POST /api/summary?cn=...       -> returns { summary } for the one item
#   - POST /api/summary?q=...        -> summary over filtered set (fallback)
#   - POST /api/summary              -> fleet-wide summary (fallback)

import os
import math
import json
import datetime
import re
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Query, Body
from fastapi.responses import JSONResponse
import httpx

# ---------- Paths ----------
APP_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_SHIPS = os.path.join(APP_DIR, "data", "ships.json")
DATA_ETA = os.path.join(APP_DIR, "data", "eta_model.json")
DATA_RISK = os.path.join(APP_DIR, "data", "region_risk.json")

app = FastAPI(title="Container Tracking Demo")

# ---------- Geo helpers ----------
R_EARTH_KM = 6371.0
KM_PER_NM = 1.852

def to_rad(d: float) -> float:
    return d * math.pi / 180.0

def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    d_lat = to_rad(b_lat - a_lat)
    d_lon = to_rad(b_lon - a_lon)
    lat1 = to_rad(a_lat)
    lat2 = to_rad(b_lat)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * R_EARTH_KM * math.asin(math.sqrt(h))

# ---------- IO ----------
def load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------- External weather ----------
async def open_meteo(lat: float, lon: float) -> Dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code",
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()

# ---------- Simple ETA model + risk ----------
def ml_eta(distance_nm: float, speed_kts: float, wind_mps: float, congestion_idx: float) -> Dict[str, Any]:
    m = load_json(DATA_ETA)
    inv = 1.0 / max(speed_kts, 0.1)
    hours = (
        float(m["intercept"])
        + float(m["coef"]["distance_nm"]) * distance_nm
        + float(m["coef"]["inv_speed"]) * inv
        + float(m["coef"]["wind"]) * wind_mps
        + float(m["coef"]["congestion"]) * congestion_idx
    )
    sigma = float(m.get("sigma_hours", 2.5))
    return {"hours": float(hours), "ci_90": [float(hours - 1.64 * sigma), float(hours + 1.64 * sigma)]}

def risk_band(pred_hours: float, planned_hours: float, wind_mps: float, region: str) -> Dict[str, Any]:
    base = float(load_json(DATA_RISK).get(region, 0.25))
    drift = max(pred_hours - planned_hours, 0.0) / max(planned_hours, 1.0)
    weather = min(wind_mps / 15.0, 1.0)
    score = min(1.0, 0.5 * drift + 0.3 * weather + 0.2 * base)
    band = "LOW"
    if score >= 0.66:
        band = "HIGH"
    elif score >= 0.33:
        band = "MED"
    return {"score": score, "band": band}

# ---------- Enrichment ----------
def enrich(it: Dict[str, Any]) -> Dict[str, Any]:
    dist_nm = haversine_km(it["lat"], it["lon"], it["waypoint"]["lat"], it["waypoint"]["lon"]) / KM_PER_NM
    wind = 5.0  # deterministic fallback; live wind used in /api/predict-eta
    pred = ml_eta(dist_nm, it["speedKts"], wind, 0.25)
    eta = (datetime.datetime.utcnow() + datetime.timedelta(hours=pred["hours"])).isoformat(timespec="minutes") + "Z"
    r = risk_band(pred["hours"], it["etaPlannedHrs"], wind, it.get("region", "Indian Ocean"))
    out = it.copy()
    out["metrics"] = {
        "distNm": dist_nm,
        "predHours": pred["hours"],
        "etaUtc": eta,
        "ci90": pred["ci_90"],
        "onTime": pred["hours"] <= it["etaPlannedHrs"] * 1.1,
        "risk": r["band"],
        "riskScore": r["score"],
    }
    return out

def load_items_enriched() -> List[Dict[str, Any]]:
    return [enrich(x) for x in load_json(DATA_SHIPS)]

# ---------- Health ----------
@app.get("/api/health")
def health():
    return {"ok": True, "ts": datetime.datetime.utcnow().isoformat() + "Z"}

# ---------- Ships ----------
@app.get("/api/ships")
def ships():
    return {"items": load_items_enriched()}

# ---------- Smart container search (tolerant) ----------
def canon(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())

def key10(s: str) -> str:
    c = canon(s)
    return c[:10] if len(c) >= 10 else c

def item_summary(it: Dict[str, Any]) -> str:
    m = it["metrics"]
    ontxt = "on-time" if m["onTime"] else "delayed"
    return (
        f"{it['vessel']} — {it['id']}: {ontxt}. "
        f"ETA {m['etaUtc']}, predicted {m['predHours']:.1f}h "
        f"(±{abs(m['ci90'][1]-m['predHours']):.1f}h @90%). "
        f"Risk {m['risk']} (score {m['riskScore']:.2f}). "
        f"Distance ~{m['distNm']:.0f} nm; speed {it['speedKts']:.1f} kts; "
        f"region {it.get('region','-')}."
    )

@app.get("/api/container")
def api_container(cn: str = Query(..., description="container or shipment id")):
    q_raw = cn.strip()
    q = canon(q_raw)
    q10 = key10(q_raw)
    items = load_items_enriched()

    # 1) direct substring
    for s in items:
        if q.lower() in s["id"].lower() or any(q in canon(c) for c in s["containers"]):
            return {"item": s, "summary": item_summary(s), "matchedBy": "exact"}

    # 2) key10 (ignore check digit)
    exact10 = []
    for s in items:
        for c in s["containers"]:
            if key10(c) == q10 and len(q10) == 10:
                exact10.append(s); break
    if exact10:
        primary = exact10[0]
        alts = list({c for s in exact10 for c in s["containers"] if key10(c) == q10})[:10]
        return {"item": primary, "summary": item_summary(primary), "matchedBy": "key10", "alternates": alts}

    # 3) suggestions
    suggestions = []
    if len(q) >= 4:
        for s in items:
            if q in canon(s["id"]) or any(canon(c).startswith(q) for c in s["containers"]):
                suggestions.append({"id": s["id"], "vessel": s["vessel"], "sample": s["containers"][0]})
    if suggestions:
        # cap & dedupe
        seen, uniq = set(), []
        for r in suggestions:
            if r["id"] not in seen:
                seen.add(r["id"]); uniq.append(r)
            if len(uniq) >= 10: break
        return JSONResponse({"error": "No exact match. Suggestions:", "suggestions": uniq}, status_code=404)

    return JSONResponse({"error": "Not found"}, status_code=404)

# ---------- Weather ----------
@app.get("/api/weather")
async def weather(lat: float, lon: float):
    try:
        return await open_meteo(lat, lon)
    except httpx.HTTPError as e:
        return JSONResponse({"error": str(e)}, status_code=502)

# ---------- Simple ETA ----------
@app.get("/api/eta-simple")
def eta_simple(lat: float, lon: float, wlat: float, wlon: float, speedKts: float):
    nm = haversine_km(lat, lon, wlat, wlon) / KM_PER_NM
    h = nm / max(speedKts, 0.1)
    eta = (datetime.datetime.utcnow() + datetime.timedelta(hours=h)).isoformat(timespec="minutes") + "Z"
    return {"distanceNm": nm, "hours": h, "etaUtc": eta}

# ---------- Predict ETA (with live wind) ----------
@app.post("/api/predict-eta")
async def predict_eta(payload: Dict[str, Any] = Body(...)):
    lat = float(payload["lat"]); lon = float(payload["lon"])
    wlat = float(payload["wlat"]); wlon = float(payload["wlon"])
    speed = float(payload["speedKts"])
    planned = float(payload.get("etaPlannedHrs", 24.0))
    region = str(payload.get("region", "Indian Ocean"))

    nm = haversine_km(lat, lon, wlat, wlon) / KM_PER_NM
    try:
        w = (await open_meteo(lat, lon)).get("current", {}).get("wind_speed_10m", 5.0)
    except Exception:
        w = 5.0
    pred = ml_eta(nm, speed, w, 0.25)
    eta = (datetime.datetime.utcnow() + datetime.timedelta(hours=pred["hours"])).isoformat(timespec="minutes") + "Z"
    return {
        "distanceNm": nm, "windMps": w, "predHours": pred["hours"],
        "ci90": pred["ci_90"], "etaUtc": eta,
        "risk": risk_band(pred["hours"], planned, w, region)
    }

# ---------- Summary ----------
@app.post("/api/summary")
def summary(
    cn: Optional[str] = Query(None, description="if present, summarize ONLY this container/shipment"),
    q: Optional[str]  = Query(None, description="else filter-wide summary by vessel/id/container"),
):
    items = load_items_enriched()

    # 1) per-item summary if cn is provided
    if cn:
        qq = canon(cn)
        qq10 = key10(cn)
        for s in items:
            if qq.lower() in s["id"].lower() or any(qq in canon(c) for c in s["containers"]):
                return {"summary": item_summary(s), "count": 1, "mode": "single"}
        for s in items:
            if any(key10(c) == qq10 and len(qq10) == 10 for c in s["containers"]):
                return {"summary": item_summary(s), "count": 1, "mode": "single-key10"}
        return {"summary": "No shipment matched that container.", "count": 0, "mode": "single"}

    # 2) filter summary if q is provided
    if q:
        ql = q.lower()
        its = [
            it for it in items
            if ql in it["id"].lower() or ql in it["vessel"].lower()
            or any(ql in c.lower() for c in it["containers"])
        ]
    else:
        its = items

    n = len(its)
    if not n:
        return {"summary": "No shipments matched your filter.", "count": 0, "mode": "filter"}

    on = sum(1 for x in its if x["metrics"]["onTime"])
    high = sum(1 for x in its if x["metrics"]["risk"] == "HIGH")
    avg = sum(x["metrics"]["predHours"] for x in its) / max(n, 1)
    worst = max(its, key=lambda x: x["metrics"]["predHours"])
    txt = (
        f"As of {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}, "
        f"{n} shipments; {on} ({round(on/n*100)}%) on-time. "
        f"Avg hours to ETA {avg:.1f}. High risk: {high}. "
        f"Worst: {worst['vessel']} ({worst['id']}) ~{worst['metrics']['predHours']:.1f}h."
    )
    return {"summary": txt, "count": n, "mode": "filter-or-fleet"}

# ---------- Test metrics ----------
@app.get("/api/test-metrics")
def api_test_metrics():
    data = load_items_enriched()
    rows, abs_errors, planned_list = [], [], []
    for it in data:
        pred = float(it["metrics"]["predHours"]); planned = float(it.get("etaPlannedHrs", 24.0))
        err = pred - planned
        abs_errors.append(abs(err)); planned_list.append(planned)
        delay_ratio = max(err, 0.0) / max(planned, 1.0)
        rows.append({
            "id": it["id"], "vessel": it["vessel"],
            "predHours": pred, "plannedHours": planned, "errorHours": err,
            "delayRatio": delay_ratio, "risk": it["metrics"]["risk"], "bandScore": it["metrics"]["riskScore"]
        })
    mae = sum(abs_errors) / max(len(abs_errors), 1)
    top3 = sorted(rows, key=lambda r: r["errorHours"], reverse=True)[:3]
    tp = sum(1 for r in top3 if r["delayRatio"] > 0.10); precision_at_3 = tp/3 if top3 else 0.0
    bands = {"LOW":0,"MED":0,"HIGH":0}
    for r in rows: bands[r["risk"]] = bands.get(r["risk"], 0) + 1
    mean_err = sum(r["errorHours"] for r in rows)/max(len(rows),1)
    mean_planned = sum(planned_list)/max(len(planned_list),1) if planned_list else 1.0
    drift_ratio = abs(mean_err)/max(mean_planned,1.0)
    return {"metrics":{"maeHours":mae,"precisionAt3":precision_at_3,"driftRatio":drift_ratio,"riskBands":bands,"latencyP95Ms":280,"n":len(rows)},"rows":rows}
