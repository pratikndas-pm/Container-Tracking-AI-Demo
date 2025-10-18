# 🚢 Pratik Das — Container Tracking AI Suite

> **An AI-powered Maritime Visibility Platform**  
> Built for predictive container tracking, ETA estimation, and risk intelligence.  
> Inspired by industry leaders such as Project44, FourKites, and DP World Cargoes Flow.

---

## 🌍 Live Demo

🔗 **Try the app:** [https://YOUR-VERCEL-URL.vercel.app](https://container-tracking-ai-demo-9h7t.vercel.app/)

🧭 Search any container from the list below (e.g. `MSCU1301003`, `MAEU6501009`, `ZIMU7002007`)  
to see:
- Map + Weather for vessel location  
- Predictive ETA  
- Dynamic KPI cards  
- LLM-style AI Summary (per container)

---

## 🧩 Overview

The **Container Tracking AI Suite** integrates live geolocation, predictive models, and natural language summaries to deliver **end-to-end shipment intelligence**.

**Core Capabilities**
- 🗺️ Real-time **Leaflet Map** (ship + next waypoint)  
- 🌦️ **Weather context** (Open-Meteo, no API key)  
- ⏱️ **AI ETA prediction** (distance, speed, congestion)  
- 🧠 **Per-container summaries** (mocked or LLM-driven)  
- 📊 **KPI dashboard:** on-time %, risk ratio, avg ETA error, total active shipments  
- 🧾 **Interactive shipment table** with search + filter

**Built with**
- Frontend: **HTML + Tailwind + Leaflet.js**
- Backend: **FastAPI (Python)**
- Hosting: **Vercel**
- Data: JSON dataset with 100 containers (10 major shipping lines)

---

## 🧠 AI Use Cases

| # | AI Use Case | Description |
|---|--------------|-------------|
| 1️⃣ | **Predictive ETA Model** | Calculates arrival times using distance, speed, and route coefficients. |
| 2️⃣ | **Risk Scoring Model** | Predicts likelihood of delay or route disruption. |
| 3️⃣ | **Container Summary AI** | Generates narrative updates per container (mock or LLM-based). |
| 4️⃣ | **Weather-aware ETA** | Adjusts ETA dynamically using Open-Meteo forecasts. |
| 5️⃣ | **Operational KPIs** | Quantifies global shipping risk and performance metrics. |

---

## 🎯 Business Problems Solved

- **Proactive Exception Management:** Detect high-risk containers before delays.  
- **Operational Optimization:** Enhance planning with predictive ETAs.  
- **Customer Transparency:** Offer human-readable summaries for every shipment.  
- **Carrier Benchmarking:** Measure on-time % and risk performance by lane.  
- **Data-driven Decisioning:** Centralized insights across 10+ carriers.

---

## 💹 Market Potential (TAM)

- 🌐 ~**900M container movements/year (2024 est.)**
- Avg. value capture: **$0.05–$0.50/container/day**
- Total Addressable Market (TAM): **>$250M globally**
- For UAE + GCC visibility providers, potential **$20–30M ARR**

---

## 💰 Pricing (USD)

| Plan | Target | Features | Price |
|------|---------|-----------|--------|
| **Starter** | SMEs / PoC | 2 users, 2k containers/mo, summaries | **$299/mo** |
| **Pro** | Mid-size | 10 users, 25k containers, webhook alerts | **$1,490/mo** |
| **Business** | Regional | 50k+ containers, private LLM endpoint | **$4,900/mo** |
| **Enterprise** | Global | Unlimited, private cloud, SLAs | **Custom** |
| **Add-on** |  — | $0.02–$0.06 per container-day (overage) | — |

> Pricing aligns to container-day tracking and inference usage.

---

## ⚙️ Models Used

| Model | Type | Description | File |
|--------|------|-------------|------|
| **ETA Model** | Linear Regression | Predict ETA using nautical distance, vessel speed, wind proxy, congestion | `data/eta_model.json` |
| **Risk Model** | Heuristic + Bayesian Priors | Predicts delay probability using region risk and ETA delta | `data/region_risk.json` |
| **Summary Model** | LLM / Template | Produces natural language shipment summary | — |

> Optionally connect `OPENAI_API_KEY` for live summaries.

---

## 🧪 Model Testing Data (Mocked KPI Results)

### 📊 Regression Results — Predictive ETA
| Metric | Result | Target |
|--------|---------|--------|
| Mean Absolute Error (MAE) | 2.1 hours | < 3.0h |
| RMSE | 3.9 hours | < 5.0h |
| R² (Goodness of Fit) | 0.92 | > 0.9 |
| ETA Drift Ratio | 0.07 | < 0.1 |
| Coverage (within ±6h) | 94% | > 90% |

### ⚠️ Risk Model Classification
| Metric | Result |
|---------|---------|
| Precision@3 | 0.88 |
| Recall | 0.81 |
| F1 Score | 0.84 |
| High-risk Accuracy | 91% |

### 🌡️ Drift Detection (Last 30 days)
| Feature | Drift | Threshold | Status |
|----------|--------|------------|---------|
| Vessel Speed | 0.03 | 0.10 | ✅ Stable |
| Weather Index | 0.06 | 0.10 | ✅ Stable |
| ETA Residual | 0.09 | 0.15 | ⚠️ Mild Drift |
| Risk Ratio | 0.05 | 0.10 | ✅ Stable |

> Continuous model monitoring ensures ETA accuracy and alert reliability over time.

---

## 📈 Success Metrics

| Category | Metric | Goal |
|-----------|---------|------|
| Business | On-time Shipments | ≥ 95% |
| Business | Exception SLA | ≥ 90% |
| Technical | API P95 Latency | < 400ms |
| Technical | ETA MAE | < 3h |
| Product | Monthly Active Ops Users | +20% MoM |
| Experience | NPS | +60 |

---



