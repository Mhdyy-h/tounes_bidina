const COLORS = {
  low: "#2ecc71",
  medium: "#f1c40f",
  high: "#e67e22",
  critical: "#e74c3c",
};

const map = L.map("map").setView([36.6, 9.2], 7);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const markers = {};

function factsHtml(zone) {
  const f = zone.factors;
  return `
    <strong>${zone.zone_name}</strong><br/>
    Risque : ${zone.risk_score}/100 (${zone.risk_level})<br/>
    Température : ${f.temperature_c.toFixed(1)} °C<br/>
    Vent : ${f.wind_kmh.toFixed(1)} km/h<br/>
    Humidité : ${f.humidity_pct.toFixed(0)} %<br/>
    Pluie récente : ${f.rain_mm.toFixed(1)} mm<br/>
    Foyers actifs (15km) : ${f.active_fires_nearby}<br/>
    NDVI : ${f.ndvi.toFixed(2)}
  `;
}

function loadingHtml() {
  return `<div style="margin-top:6px;color:#8fa3b3"><em>Chargement du modèle IA…</em></div>`;
}

function mlDetailsHtml(prediction) {
  const ndviNote = prediction.source_datasets
    ? `<div style="margin-top:6px;font-size:11px;color:#8fa3b3">Source NDVI : ${prediction.source_datasets.ndvi}</div>`
    : "";

  if (!prediction.ml) {
    return (
      `<div style="margin-top:6px;color:#8fa3b3"><em>Modèle IA indisponible - score basé sur la formule de secours.</em></div>` +
      ndviNote
    );
  }
  const ml = prediction.ml;
  return `
    <div style="margin-top:6px;border-top:1px solid #2c3b48;padding-top:6px">
      <strong>Modèle IA :</strong> ${ml.prediction === "fire" ? "incendie probable" : "pas d'incendie probable"}
      (probabilité ${(ml.fire_probability * 100).toFixed(0)}%, confiance ${(ml.confidence * 100).toFixed(0)}%)<br/>
      <span style="font-size:11px;color:#8fa3b3">${ml.explanation}</span>
    </div>
    ${ndviNote}
  `;
}

const FORECAST_DAY_LABELS = ["J+1", "J+2", "J+3"];

function forecastStripHtml(forecast) {
  if (!forecast || !forecast.forecast_available || forecast.days.length === 0) {
    return `<div style="margin-top:6px;font-size:11px;color:#8fa3b3">Prévision indisponible pour le moment.</div>`;
  }
  const items = forecast.days
    .map((d, i) => {
      const color = COLORS[d.risk_level] || "#7fd0ff";
      return `
        <div style="text-align:center;flex:1">
          <div style="font-size:10px;color:#8fa3b3">${FORECAST_DAY_LABELS[i] || d.date}</div>
          <div style="width:14px;height:14px;border-radius:50%;background:${color};margin:3px auto"></div>
          <div style="font-size:10px">${d.temperature_c.toFixed(0)}°C</div>
        </div>`;
    })
    .join("");
  return `
    <div style="margin-top:6px;border-top:1px solid #2c3b48;padding-top:6px">
      <div style="font-size:11px;color:#8fa3b3;margin-bottom:2px">Prévision 3 jours (Open-Meteo réel) :</div>
      <div style="display:flex;gap:4px">${items}</div>
    </div>
  `;
}

function applyRiskUpdate(zones) {
  zones.forEach((zone) => {
    const color = COLORS[zone.risk_level] || "#7fd0ff";
    if (markers[zone.zone_id]) {
      markers[zone.zone_id].setStyle({ color, fillColor: color });
      markers[zone.zone_id].zoneData = zone;
      if (markers[zone.zone_id].isPopupOpen()) {
        markers[zone.zone_id].setPopupContent(factsHtml(zone));
      }
    } else {
      const marker = L.circleMarker([zone.lat, zone.lon], {
        radius: 12,
        color,
        fillColor: color,
        fillOpacity: 0.8,
        weight: 2,
      }).addTo(map);
      marker.zoneData = zone;
      marker.bindPopup(factsHtml(zone));
      marker.on("popupopen", async () => {
        marker.setPopupContent(factsHtml(marker.zoneData) + loadingHtml());
        try {
          const [predRes, forecastRes] = await Promise.all([
            fetch(`/api/predict/${zone.zone_id}`),
            fetch(`/api/forecast/${zone.zone_id}`),
          ]);
          const prediction = await predRes.json();
          const forecast = await forecastRes.json();
          marker.setPopupContent(
            factsHtml(marker.zoneData) + mlDetailsHtml(prediction) + forecastStripHtml(forecast)
          );
        } catch (err) {
          console.error("Failed to fetch ML prediction/forecast", err);
          marker.setPopupContent(factsHtml(marker.zoneData));
        }
      });
      markers[zone.zone_id] = marker;
    }
  });
}

async function refreshRisk() {
  try {
    const res = await fetch("/api/risk");
    applyRiskUpdate(await res.json());
  } catch (err) {
    console.error("Failed to refresh risk data", err);
  }
}

let livePollFallback = null;

function startLiveUpdates() {
  if (!window.EventSource) {
    console.warn("EventSource unsupported, falling back to polling");
    livePollFallback = setInterval(refreshRisk, 15000);
    return;
  }

  const source = new EventSource("/api/risk/stream");
  source.onmessage = (event) => {
    connectionStatusEl.textContent = "🟢 Live";
    applyRiskUpdate(JSON.parse(event.data));
  };
  source.onerror = () => {
    connectionStatusEl.textContent = "🟡 Reconnexion…";
    if (source.readyState === EventSource.CLOSED && !livePollFallback) {
      console.warn("SSE connection closed permanently, falling back to polling");
      livePollFallback = setInterval(refreshRisk, 15000);
    }
    // readyState CONNECTING means the browser is auto-retrying - let it.
  };
}

const connectionStatusEl = document.getElementById("connection-status");
const triggerScenarioBtn = document.getElementById("trigger-scenario");
const resetScenarioBtn = document.getElementById("reset-scenario");

async function withButtonBusy(button, action) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "⏳ " + originalText;
  try {
    await action();
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

triggerScenarioBtn.addEventListener("click", () =>
  withButtonBusy(triggerScenarioBtn, async () => {
    await fetch("/api/scenario/override", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        zone_id: "ain_draham",
        ndvi: 0.15,
        temperature_c: 41,
        wind_kmh: 38,
        humidity_pct: 12,
        active_fires_nearby: 2,
      }),
    });
    await refreshRisk();
  })
);

resetScenarioBtn.addEventListener("click", () =>
  withButtonBusy(resetScenarioBtn, async () => {
    await fetch("/api/scenario/reset", { method: "POST" });
    await refreshRisk();
  })
);

const ndviStatusEl = document.getElementById("ndvi-status");
const refreshNdviBtn = document.getElementById("refresh-ndvi");

async function refreshNdviStatus() {
  try {
    const res = await fetch("/api/ndvi/status");
    const status = await res.json();
    const realCount = status.zones.filter((z) => z.is_real).length;

    if (status.real_cache_available) {
      ndviStatusEl.textContent = `NDVI : réel pour ${realCount}/${status.zones.length} zones (MAJ ${new Date(status.fetched_at).toLocaleString("fr-FR")})`;
    } else if (!status.earthdata_credentials_configured) {
      ndviStatusEl.textContent = "NDVI : simulé (NASA Earthdata non configuré)";
    } else {
      ndviStatusEl.textContent = "NDVI : identifiants configurés, pas encore récupéré";
    }
  } catch (err) {
    ndviStatusEl.textContent = "NDVI : statut indisponible";
  }
}

refreshNdviBtn.addEventListener("click", async () => {
  refreshNdviBtn.disabled = true;
  const res = await fetch("/api/ndvi/refresh", { method: "POST" });
  const data = await res.json();
  ndviStatusEl.textContent = data.message;
  setTimeout(() => {
    refreshNdviBtn.disabled = false;
    refreshNdviStatus();
  }, 5000);
});

startLiveUpdates();
refreshNdviStatus();
setInterval(refreshNdviStatus, 30000);
