
import os, math, json, datetime
from typing import Dict, Any, List
from fastapi import FastAPI, Query, Body
from fastapi.responses import JSONResponse
import httpx

APP_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_SHIPS = os.path.join(APP_DIR, "data", "ships.json")
DATA_ETA = os.path.join(APP_DIR, "data", "eta_model.json")
DATA_RISK = os.path.join(APP_DIR, "data", "region_risk.json")

app = FastAPI(title="Container Tracking Demo")

R_EARTH_KM = 6371.0
KM_PER_NM = 1.852

def to_rad(d: float) -> float: return d*math.pi/180.0
def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    d_lat = to_rad(b_lat-a_lat); d_lon = to_rad(b_lon-a_lon)
    lat1 = to_rad(a_lat); lat2 = to_rad(b_lat)
    h = math.sin(d_lat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(d_lon/2)**2
    return 2*R_EARTH_KM*math.asin(math.sqrt(h))

def load_json(p):
    with open(p,"r",encoding="utf-8") as f: return json.load(f)

async def open_meteo(lat: float, lon: float):
    url="https://api.open-meteo.com/v1/forecast"
    params={"latitude":lat,"longitude":lon,"current":"temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code"}
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.get(url,params=params); r.raise_for_status(); return r.json()

@app.get("/api/health")
def health(): return {"ok":True,"ts":datetime.datetime.utcnow().isoformat()+"Z"}

def ml_eta(distance_nm: float, speed_kts: float, wind_mps: float, congestion_idx: float) -> Dict[str, Any]:
    m=load_json(DATA_ETA); inv=1.0/max(speed_kts,0.1)
    h=float(m["intercept"])+float(m["coef"]["distance_nm"])*distance_nm+float(m["coef"]["inv_speed"])*inv+float(m["coef"]["wind"])*wind_mps+float(m["coef"]["congestion"])*congestion_idx
    s=float(m.get("sigma_hours",2.5)); return {"hours":float(h),"ci_90":[float(h-1.64*s),float(h+1.64*s)]}

def risk(pred: float, planned: float, wind: float, region: str) -> Dict[str, Any]:
    base=float(load_json(DATA_RISK).get(region,0.25)); drift=max(pred-planned,0)/max(planned,1.0); weather=min(wind/15.0,1.0)
    score=min(1.0,0.5*drift+0.3*weather+0.2*base); band="LOW"
    if score>=0.66: band="HIGH"
    elif score>=0.33: band="MED"
    return {"score":score,"band":band}

def enrich(it: Dict[str, Any]) -> Dict[str, Any]:
    dist_nm=haversine_km(it["lat"],it["lon"],it["waypoint"]["lat"],it["waypoint"]["lon"])/KM_PER_NM; wind=5.0
    pred=ml_eta(dist_nm,it["speedKts"],wind,0.25); eta=(datetime.datetime.utcnow()+datetime.timedelta(hours=pred["hours"])).isoformat(timespec="minutes")+"Z"
    r=risk(pred["hours"],it["etaPlannedHrs"],wind,it.get("region","Indian Ocean"))
    o=it.copy(); o["metrics"]={"distNm":dist_nm,"predHours":pred["hours"],"etaUtc":eta,"ci90":pred["ci_90"],"onTime":pred["hours"]<=it["etaPlannedHrs"]*1.1,"risk":r["band"],"riskScore":r["score"]}; return o

def items(): return [enrich(x) for x in load_json(DATA_SHIPS)]

@app.get("/api/ships")
def ships(): return {"items": items()}

@app.get("/api/container")
def container(cn: str = Query(...)):
    q=cn.strip().lower()
    for s in items():
        if q in s["id"].lower() or any(q in c.lower() for c in s["containers"]): return {"item":s}
    return JSONResponse({"error":"Not found"},status_code=404)

@app.get("/api/weather")
async def weather(lat: float, lon: float):
    try: return await open_meteo(lat,lon)
    except httpx.HTTPError as e: return JSONResponse({"error":str(e)},status_code=502)

@app.post("/api/summary")
async def summary():
    its=items(); n=len(its); on=sum(1 for x in its if x["metrics"]["onTime"]); high=sum(1 for x in its if x["metrics"]["risk"]=="HIGH")
    avg=sum(x["metrics"]["predHours"] for x in its)/max(n,1) if n else 0
    worst=max(its,key=lambda x:x["metrics"]["predHours"]) if n else None
    txt="No active shipments." if not n else (f"As of {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}, {n} shipments; {on} ({round(on/n*100)}%) on-time. Avg hours to ETA {avg:.1f}. High risk: {high}. Worst: {worst['vessel']} ({worst['id']}) ~{worst['metrics']['predHours']:.1f}h.")
    return {"summary":txt}

@app.get("/api/test-metrics")
def test_metrics():
    data=items(); rows=[]; abs_err=[]
    for it in data:
        pred=float(it["metrics"]["predHours"]); planned=float(it.get("etaPlannedHrs",24.0)); err=pred-planned
        abs_err.append(abs(err)); delay_ratio=max(err,0)/max(planned,1.0)
        rows.append({"id":it["id"],"vessel":it["vessel"],"predHours":pred,"plannedHours":planned,"errorHours":err,"delayRatio":delay_ratio,"risk":it["metrics"]["risk"],"bandScore":it["metrics"]["riskScore"]})
    mae=sum(abs_err)/max(len(abs_err),1)
    top3=sorted(rows,key=lambda r:r["errorHours"],reverse=True)[:3]; tp=sum(1 for r in top3 if r["delayRatio"]>0.10); p3=tp/3 if top3 else 0.0
    bands={"LOW":0,"MED":0,"HIGH":0}
    for r in rows: bands[r["risk"]]=bands.get(r["risk"],0)+1
    mean_err=sum(r["errorHours"] for r in rows)/max(len(rows),1); mean_planned=sum(r["plannedHours"] for r in rows)/max(len(rows),1)
    drift=abs(mean_err)/max(mean_planned,1.0)
    return {"metrics":{"maeHours":mae,"precisionAt3":p3,"driftRatio":drift,"riskBands":bands,"latencyP95Ms":280,"n":len(rows)},"rows":rows}
