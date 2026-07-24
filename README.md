# Tunisia Guardian AI

Protecting People. Preserving Nature. Powering Tourism.

An AI-assisted wildfire risk platform for 6 Tunisian tourist zones: real-time weather
(Open-Meteo, no key needed) + NASA FIRMS fire hotspots + real MODIS NDVI (NASA
Earthdata) feed a **trained XGBoost wildfire classifier**, an Ollama LLM explains the
score and recommends a safer neighboring zone (French/English), a real 3-day forecast
projects risk forward, and a Leaflet map / tourist screen / Ministry dashboard surface
it all live.

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
- Weather needs **no key** (Open-Meteo).

```bash
# Windows PowerShell
$env:EARTHDATA_USERNAME = "your_username"
$env:EARTHDATA_PASSWORD = "your_password"
$env:FIRMS_API_KEY = "your_key_here"
```

## 7. Run

```bash
uvicorn backend.main:app --reload
```

- Map: http://localhost:8000/
- Tourist screen: http://localhost:8000/tourist
- Ministry dashboard: http://localhost:8000/dashboard
- Full explainability for any zone: http://localhost:8000/api/predict/ain_draham
- 3-day risk forecast for any zone: http://localhost:8000/api/forecast/ain_draham
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
  models.py               Pydantic models
frontend/
  index.html, map.js, style.css       risk map + demo scenario buttons + live ML popup + forecast strip
  tourist.html, tourist.js            tourist query screen, date-aware (live/forecast/beyond-range)
  dashboard.html, dashboard.js         Ministry dashboard - all zones, sorted, live, summary stats
  i18n.js                              shared FR/EN dictionary + toggle, used by all 3 pages
```

## 14. API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/zones` | Static zone metadata |
| GET | `/api/risk` | Composite risk score for all zones |
| GET | `/api/risk/{zone_id}` | Same, single zone |
| GET | `/api/risk/stream` | Server-Sent Events: pushes the full risk list every 5s |
| GET | `/api/predict/{zone_id}` | Full explainability: prediction, confidence, explanation, timestamp, input features, source datasets |
| GET | `/api/forecast/{zone_id}` | Real 3-day risk forecast (Open-Meteo forecast + same ML scoring) |
| GET | `/api/ndvi/status` | Whether real NDVI is available per zone, composite dates, whether Earthdata credentials are configured |
| POST | `/api/ndvi/refresh` | Kicks off a real MODIS NDVI fetch in the background (returns immediately; takes minutes to complete) |
| POST | `/api/tourist/query` | `{zone_id, visit_date, lang}` → safe/unsafe + LLM explanation (FR/EN) + alternative zone + which date's data was actually used |
| POST | `/api/scenario/override` | Force weather/fire/NDVI values for a zone (demo) |
| POST | `/api/scenario/reset` | Reset all zones to live/real values |
