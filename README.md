# Tunisia Guardian AI

Protecting People. Preserving Nature. Powering Tourism.

An AI-assisted risk platform for 6 Tunisian tourist zones, built around a **7-agent
system**: Fire (real ML), Flood, Water, Electricity, Tourism, Emergency, and an XAI
agent that explains every prediction factor-by-factor. Real-time weather (Open-Meteo,
no key needed), NASA FIRMS fire hotspots, real MODIS NDVI (NASA Earthdata), a real
crowd-sourced electricity outage feed (Famma Dhaw), and real OSRM road routing feed a
**trained XGBoost wildfire classifier** plus the other domain agents. A Leaflet map,
tourist screen, full multi-agent tourist portal, hotel resilience portal, and Ministry
operations dashboard surface it all live.

## 0. What's new: the multi-agent platform (read this first)

This build grew from a single-hazard (wildfire) MVP into a 7-agent operations
platform. Everything below is real and independently verified, with the same
honesty discipline as the original fire-risk work - simulated data is always
labeled `is_simulated: true` and never silently presented as real.

- **Zone-ID mismatch fixed.** The flood/water/electricity/emergency/XAI agents'
  simulated lookup tables were originally keyed to a 10-city set that didn't match
  this app's actual 6 zones (`tabarka`, `ain_draham`, `bulla_regia`, `dougga`,
  `ichkeul`, `hammamet`) - only 2 of 6 zones had real entries, the other 4 silently
  got generic fallback numbers. All 6 zones now have real, geographically-reasoned
  entries (e.g. Dougga is correctly modeled as an elevated UNESCO hilltop site with
  low flood risk; Ichkeul as a lake basin near Bizerte).
- **Famma Dhaw electricity integration** (`backend/famma_dhaw_client.py`) - real,
  live, crowd-sourced outage data for Tunisia, via the same public Supabase
  endpoint their own website's frontend calls (no official API exists; this is
  unofficial community data, always labeled as such - "cross-reference with
  STEG" per their own disclaimer). 3 of 6 zones (`ain_draham`, `tabarka`,
  `hammamet`) match exactly; the other 3 map to their nearest tracked
  municipality, explicitly flagged as an approximation.
- **Hotel Resilience Dashboard** (`/hotel-portal`) - the first real database in
  this project (`backend/db.py`, SQLite). Hotels self-report electricity/water/
  internet/generator/battery/solar/autonomy/rooms, which persists across
  restarts. `GET /api/hotels/resilience/summary` aggregates: % operational,
  generator/battery/solar coverage, most resilient zone, rooms available in
  currently-safe zones. `GET /api/hotels/alternative/{zone}/{hotel}` implements
  the exact requested behavior: if a hotel lacks power, it recommends an
  operational alternative in the same zone, then neighboring zones.
- **Smart Tourist Route Planner** (`backend/route_planner.py`) - real road
  routing via OSRM's public API (no key), not a fake straight line. Requests
  OSRM's real alternative-route feature, then picks whichever alternative's
  actual road geometry passes farthest from zones currently at high/critical
  fire risk. If OSRM has no genuine alternative for a given trip, that's
  reported honestly rather than inventing one - verified live for several
  origin/destination pairs, including one where a critical zone's proximity was
  correctly detected but no real alternative existed.
- **Automatic hotel email notifications** (`backend/email_client.py`) - real
  SMTP sending, gated behind `SMTP_HOST`/`SMTP_USERNAME`/`SMTP_PASSWORD` you
  must supply (same pattern as every other credential in this project). Without
  them configured, every notification is logged in full instead of silently
  dropped, and the API response says `"sent": false, "method": "log_only"`
  rather than claiming success.
- **French/English toggle** now covers this whole platform, not just the
  original 3 pages.

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Train the wildfire model (required for real ML predictions)

```bash
python -m training.train_fire
```

This downloads nothing at runtime — it trains on the dataset already vendored at
`data/raw/Algerian_forest_fires_dataset_UPDATE.csv` — and writes
`models/wildfire_model.pkl` + `models/wildfire_model_meta.json` (metrics, feature
importances, dataset citation). **If you skip this step**, the app does not break:
every risk computation automatically falls back to the rule-based formula in
`backend/risk_engine.py`, and `/api/predict/{zone_id}` returns `"ml": null` with
`source_datasets.ml_model` explicitly saying the model isn't available — never a
silent placeholder number.

## 3. Real-time weather — works out of the box, no key needed

Weather (temperature, wind, humidity, rain) comes from
[Open-Meteo](https://open-meteo.com), which requires **no API key and no signup at
all**. This is live, real data from the moment you start the server — that's why
Aïn Draham correctly shows ~34°C in July instead of a stale constant.

## 4. Real NDVI via NASA Earthdata (optional but recommended)

NDVI (vegetation dryness) defaults to a simulated file
(`data/ndvi_simulated.json`) unless you connect real satellite data:

1. Create a free account at https://urs.earthdata.nasa.gov/ (NASA Earthdata Login).
2. Set `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` as environment variables.
3. Fetch real NDVI:
   ```bash
   python -m training.fetch_real_ndvi
   ```
   Or, with the server running, `POST /api/ndvi/refresh` (also exposed as the
   "🛰️ Refresh satellite NDVI" button on the map).

**Read this before expecting instant results:** this calls NASA's AppEEARS API,
which processes MODIS satellite data as an asynchronous task — it typically takes
**several minutes**, sometimes longer under load. This is not a bug or something I
cut a corner on: **no vegetation index from any satellite is truly real-time.**
MOD13Q1 is a 250m, **16-day composite** product with its own processing lag on top
— the "most recent real NDVI" is inherently a few weeks old, industry-wide. This
build fetches the actual most-recent composite and labels it with its real
composite date, rather than pretending to have something that doesn't exist.

If Earthdata credentials aren't set, or the fetch hasn't been run yet, or it fails,
the app transparently falls back to the simulated file — check
`GET /api/ndvi/status` or `source_datasets.ndvi` in any `/api/predict/{zone_id}`
response to see exactly which one is in effect right now.

## 5. (Optional) Ollama for LLM prose explanations

If Ollama isn't installed or running, the tourist-facing explanation automatically
falls back to a deterministic French template built from the real risk factors —
nothing breaks. To enable live LLM explanations:

```bash
ollama pull llama3.1:8b
ollama serve
```

## 6. Environment variables

- `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` — free account at
  https://urs.earthdata.nasa.gov/, needed for real NDVI (section 4). Without these,
  NDVI stays simulated.
- `FIRMS_API_KEY` — free MAP_KEY from https://firms.modaps.eosdis.nasa.gov/api/map_key/
  (just an email signup). Without it, active fire count defaults to 0.
- `SMTP_HOST` / `SMTP_PORT` (default 587) / `SMTP_USERNAME` / `SMTP_PASSWORD` /
  `SMTP_FROM_EMAIL` — needed for real hotel hazard-alert emails (section 0). Any
  standard SMTP provider works (Gmail app password, SendGrid, your own mail
  server, etc.). Without these, notifications are logged in full instead of sent
  — never silently dropped, never falsely reported as sent.
- Weather needs **no key** (Open-Meteo). Famma Dhaw electricity data needs **no
  key** (public endpoint). OSRM routing needs **no key** (public demo server).

```bash
# Windows PowerShell
$env:EARTHDATA_USERNAME = "your_username"
$env:EARTHDATA_PASSWORD = "your_password"
$env:FIRMS_API_KEY = "your_key_here"
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_USERNAME = "you@gmail.com"
$env:SMTP_PASSWORD = "your_app_password"
$env:SMTP_FROM_EMAIL = "you@gmail.com"
```

## 7. Run

```bash
uvicorn backend.main:app --reload
```

- Map: http://localhost:8000/
- Tourist screen: http://localhost:8000/tourist
- Full multi-agent tourist portal (destinations, route planner, alerts, XAI): http://localhost:8000/tourist-portal
- Hotel resilience portal (declare status): http://localhost:8000/hotel-portal
- Ministry operations dashboard: http://localhost:8000/dashboard
- Full explainability for any zone: http://localhost:8000/api/predict/ain_draham
- 3-day risk forecast for any zone: http://localhost:8000/api/forecast/ain_draham
- Unified multi-agent dashboard for any zone: http://localhost:8000/api/tourist/dashboard/ain_draham
- NDVI data-source status: http://localhost:8000/api/ndvi/status

## 8. Demo scenario

Click **"Trigger fire scenario (Aïn Draham)"** on the map to force elevated
temperature/wind/humidity/rain/active-fires and dry NDVI for Aïn Draham — its risk
score and marker color update immediately (the button re-fetches). Click **"Reset
scenario"** to restore all zones to live/real values.

## 9. Performance

`/api/risk` computes weather + fires + ML inference for all 6 zones. Two
optimizations, measured on this machine:

- **Parallelized per-zone fetching** (`asyncio.gather` instead of a sequential
  loop): cold-cache latency dropped from **~7.5s to ~2.9s**.
- **Short-lived server-side cache** for weather (60s) and FIRMS (5min), since
  neither changes meaningfully faster than that: warm-cache latency dropped to
  **~10-25ms** — a 300-700x speedup for the common case (the map polls/streams
  far more often than the underlying data actually changes).
- **Live updates via Server-Sent Events** (`GET /api/risk/stream`) replace
  client-side polling: the map now receives a push every 5s instead of issuing
  its own request every 15s, and multiple open tabs/viewers all stay in sync
  automatically. If `EventSource` isn't available or the stream drops
  permanently, the frontend transparently falls back to plain polling - same
  "never hard-fail" pattern as every other layer of this app.

## 10. Forecast, Ministry dashboard, and bilingual UI

- **3-day risk forecast, not just current conditions.** `GET /api/forecast/{zone_id}`
  runs a real Open-Meteo daily forecast through the exact same ML composite scoring
  as the live map (`backend/risk_forecast.py`). NDVI and active-fire count are held
  at today's value for the whole window (neither is forecastable - see the honesty
  note in that file); only the weather-driven part of the score is truly
  forward-looking, and that limitation is stated in the API response itself, not
  hidden. The map popup shows a 3-day mini-trend per zone.
- **The tourist date field is now load-bearing.** Previously `visit_date` was
  accepted but never used - every query silently used today's live data regardless
  of the date picked. Now: dates 1-3 days out use the real forecast for that
  specific day; today uses live data; anything further out honestly falls back to
  "no reliable forecast that far out, showing current conditions" (`backend/main.py`,
  `_resolve_zone_risk_for_date` / `MAX_RELIABLE_FORECAST_DAYS`) rather than either
  ignoring the date or fabricating a long-range forecast Open-Meteo would technically
  return but that isn't meteorologically reliable.
- **Ministry dashboard** (`/dashboard`): all zones sorted by risk, summary stats,
  live via the same SSE stream as the map - the "authorities get a decision view"
  half of the original pitch, not just the tourist-facing half. The "tourist
  confidence" figure shown is explicitly labeled as `100 - risk_score`, a simplified
  preview, not a separately modeled metric.
- **French/English toggle** on every page (persisted via `localStorage`), covering
  all static UI chrome and the tourist screen's LLM/fallback explanation (which is
  genuinely generated in the selected language server-side, not translated
  client-side - see `lang` param on `POST /api/tourist/query`). Scope cut, stated
  explicitly rather than silently dropped: the small supplementary strings inside
  the map's ML popup (the data-driven "why" sentence, `source_datasets` labels) stay
  French-only in this build. Arabic was considered but deferred - proper support
  needs an RTL layout, not just translated strings, and doing that half-way under
  time pressure would look worse than not doing it.

## 11. What's real vs. simulated (read this before a judge asks)

| Signal | Source | Status |
|---|---|---|
| Wildfire probability | XGBoost classifier trained on the **Algerian Forest Fires Dataset** (Abid, F., Zenodo 2022, DOI [10.5281/zenodo.6515969](https://doi.org/10.5281/zenodo.6515969), CC-BY-4.0) | **Real, trained model.** 243 real historical daily records (Bejaia + Sidi Bel-abbes regions, Algeria, June–Sept 2012). Held-out test metrics: accuracy 0.86, ROC-AUC 0.94 (see `models/wildfire_model_meta.json`). |
| Temperature / wind / humidity / rain | Open-Meteo | **Real, live, no key needed.** Only falls back to a fixed default if the network call itself fails. |
| Active fires nearby | NASA FIRMS satellite hotspot detections (haversine-filtered) | **Real, live**, if `FIRMS_API_KEY` is set; otherwise an explicitly-flagged fallback default. |
| NDVI (vegetation dryness) | NASA Earthdata/AppEEARS, MODIS MOD13Q1.061 (real) or `data/ndvi_simulated.json` (simulated) | **Real if `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD` are set and `python -m training.fetch_real_ndvi` has been run**, labeled with its actual composite date; otherwise explicitly labeled SIMULATED. Never silently one or the other — check `/api/ndvi/status`. |
| LLM prose explanation | Ollama (`llama3.1:8b`) | Real local LLM call when available; deterministic template fallback (built from the same real numbers) if not. |

**Honesty limitation, stated plainly:** there is no public labeled Tunisian
wildfire dataset, so the trained model uses a real Mediterranean fire-weather
dataset from Algeria as a proxy — not literal Tunisian ground truth. It's the same
feature family (temperature/humidity/wind/rain) used operationally in
Fire-Weather-Index-style systems, which is why it transfers reasonably, but this is
disclosed rather than glossed over. `GET /api/predict/{zone_id}` always returns
`source_datasets` naming exactly where every number came from, including whether
it's live, real-but-cached, simulated, or a demo override.

## 12. Design decisions

- **No SQLite/DB layer.** Nothing in this MVP needs query history or persistence
  beyond the NDVI cache/scenario files (JSON on disk) and the trained model file.
- **Every external dependency has a fallback** (Open-Meteo, FIRMS, Ollama, the
  MODIS NDVI fetch, and the ML model itself) so a dead network, a crashed Ollama
  process, or a never-trained model never crashes the demo.
- **Real NDVI is fetched asynchronously, never inline with a request.** AppEEARS
  point tasks take minutes; blocking an HTTP request on that would be bad
  architecture, not just slow. `training/fetch_real_ndvi.py` (or
  `POST /api/ndvi/refresh`, which runs it as a background task) refreshes a cache
  file that live requests read from instantly.
- **Composite score, not a black box.** `/api/risk` score = ML fire probability
  (0-50 pts) + live FIRMS active-fire count (0-30 pts) + NDVI, real or simulated
  (0-20 pts). The exact weights are documented in `backend/ml_risk.py`, not hidden.

## 13. Project structure

```
data/
  raw/Algerian_forest_fires_dataset_UPDATE.csv   real dataset, MD5-verified against Zenodo
  processed/algerian_forest_fires_clean.csv       output of preprocessing/clean_fire_data.py
  zones.json                                       6 hardcoded Tunisian zones
  ndvi_simulated.json                              simulated NDVI baseline (used if real fetch unavailable)
  ndvi_real_cache.json                             real MODIS NDVI cache (generated by fetch_real_ndvi.py)
preprocessing/
  clean_fire_data.py    parses the messy raw CSV (two regions, header repeats, data typos)
training/
  train_fire.py         trains XGBoost, saves model + metadata + metrics
  fetch_real_ndvi.py     fetches real MODIS NDVI via NASA Earthdata/AppEEARS
models/
  wildfire_model.pkl          trained classifier (generated by training/train_fire.py)
  wildfire_model_meta.json    dataset citation, metrics, feature importances, class stats
inference/
  predict.py             loads the model once, serves predict_fire_risk()
backend/
  main.py              FastAPI app + all routes, /api/risk/stream SSE endpoint
  cache.py                tiny TTL cache used by weather/FIRMS clients
  ml_risk.py             composite score = ML + FIRMS + NDVI, documented weights
  risk_engine.py          rule-based FALLBACK scorer (used only if the model is unavailable)
  weather_client.py       Open-Meteo wrapper (real-time, no key, with fallback)
  firms_client.py         NASA FIRMS wrapper (with fallback, haversine filtering, reports is_live)
  earthdata_client.py     NASA Earthdata/AppEEARS client (login, submit/poll/download MODIS NDVI task)
  ndvi_cache.py           shared real-NDVI cache read/write, used by the CLI script and live endpoint
  llm_agent.py            Ollama explanation + recommendation (with fallback)
  scenario.py             weather/fire/NDVI factor overrides for the demo, real-vs-simulated NDVI resolution
  risk_forecast.py         3-day forecast: same ML scoring, real Open-Meteo forecast weather
  famma_dhaw_client.py     real crowd-sourced electricity outage data (Supabase, no official API)
  db.py                    SQLite persistence - hotels table (the first real DB use case)
  hotel_service.py         resilience aggregation + hazard-aware alternative-hotel logic
  route_planner.py         real OSRM road routing + hazard-aware alternative-route selection
  email_client.py          real SMTP delivery for hotel notifications, log-only fallback
  models.py                Pydantic models
  agents/
    flood_agent.py water_agent.py electricity_agent.py    domain risk agents (simulated, labeled)
    tourism_agent.py emergency_agent.py                     recommendation + resource allocation
    xai_agent.py notification_agent.py                      explainability + stakeholder alerts
frontend/
  index.html, map.js, style.css       risk map + demo scenario buttons + live ML popup + forecast strip
  tourist.html, tourist.js            simple tourist query screen, date-aware
  tourist_portal.html, tourist_portal.js   full multi-agent portal - destinations, route planner, alerts, XAI
  hotel_portal.html, hotel_portal.js   hotel self-declaration form + live status table
  dashboard.html, dashboard.js         Ministry dashboard - agents, hotel resilience, notifications
  i18n.js                              shared FR/EN dictionary + toggle, used by all pages
```

## 14. API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/zones` | Static zone metadata |
| GET | `/api/risk` | Composite risk score for all zones |
| GET | `/api/risk/{zone_id}` | Same, single zone |
| GET | `/api/agents/{flood\|water\|electricity}/{zone_id}` | Individual domain agent (simulated, labeled) |
| GET | `/api/agents/tourism/{zone_id}` | Safe destinations, smart routing hints, festivals |
| GET | `/api/agents/emergency/{zone_id}` | Resource allocation, intervention sequence |
| GET | `/api/agents/xai/{fire\|flood\|water\|electricity}/{zone_id}` | Factor-by-factor explanation |
| GET | `/api/agents/notifications/{zone_id}` | Stakeholder alerts for a zone |
| GET | `/api/agents/status` | Global agent summary across all zones |
| GET | `/api/tourist/dashboard/{zone_id}` | All 6 agents run in parallel, unified response |
| GET | `/api/hotels/{zone_id}` | Declared hotels in a zone |
| POST | `/api/hotels/declare` | Hotel self-reports operational status (upsert) |
| DELETE | `/api/hotels/{zone_id}/{hotel_name}` | Remove a declaration |
| GET | `/api/hotels/resilience/summary` | Aggregate resilience stats across all zones |
| GET | `/api/hotels/alternative/{zone_id}/{hotel_name}` | Real hazard-aware alternative-hotel recommendation |
| GET | `/api/route/airports` | Real airport coordinates for route planning |
| GET | `/api/route/plan?origin=&destination=` | Real OSRM route + hazard-aware alternative selection |
| POST | `/api/notifications/send/{zone_id}` | Sends (or logs) real hazard emails to declared hotels |
| GET | `/api/risk/stream` | Server-Sent Events: pushes the full risk list every 5s |
| GET | `/api/predict/{zone_id}` | Full explainability: prediction, confidence, explanation, timestamp, input features, source datasets |
| GET | `/api/forecast/{zone_id}` | Real 3-day risk forecast (Open-Meteo forecast + same ML scoring) |
| GET | `/api/ndvi/status` | Whether real NDVI is available per zone, composite dates, whether Earthdata credentials are configured |
| POST | `/api/ndvi/refresh` | Kicks off a real MODIS NDVI fetch in the background (returns immediately; takes minutes to complete) |
| POST | `/api/tourist/query` | `{zone_id, visit_date, lang}` → safe/unsafe + LLM explanation (FR/EN) + alternative zone + which date's data was actually used |
| POST | `/api/scenario/override` | Force weather/fire/NDVI values for a zone (demo) |
| POST | `/api/scenario/reset` | Reset all zones to live/real values |
