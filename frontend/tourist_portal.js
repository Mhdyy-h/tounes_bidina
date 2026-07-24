/**
 * Tourist Portal JS — Tunisia Guardian AI Multi-Agent Platform
 * Handles: zone selection, agent dashboard, destination grid, trip planner,
 *           alerts feed, XAI panel, Leaflet map integration
 */

// ─── Destination emoji map ────────────────────────────────────────────────────
const DEST_EMOJI = {
  beach:              "🏖️",
  archaeological_site:"🏛️",
  nature:             "🌿",
  cultural:           "🏘️",
  village:            "🏡",
};

// ─── State ────────────────────────────────────────────────────────────────────
let allZones     = [];
let currentZone  = null;
let dashboardData = null;
let allNotifications = [];
let map          = null;
let markers      = {};

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await Promise.all([loadZones(), loadGlobalDestinations()]);
  setupTabs();
  setupAlertsFilter();
  setupXaiSelector();
  setupPlannerForm();
  initMap();
});

// ─── Load Zones ───────────────────────────────────────────────────────────────
async function loadZones() {
  try {
    const res = await fetch("/api/zones");
    allZones = await res.json();
    renderZoneSelector(allZones);
    populatePlannerZoneSelect(allZones);
    await refreshGlobalBanner();
  } catch (err) {
    console.error("Failed to load zones:", err);
  }
}

function renderZoneSelector(zones) {
  const el = document.getElementById("zone-selector");
  el.innerHTML = zones.map(z => `
    <button class="zone-btn" id="zone-btn-${z.id}" onclick="selectZone('${z.id}')">
      <div class="zone-name">${z.name}</div>
      <div class="zone-risk" id="zone-risk-${z.id}">Loading…</div>
    </button>
  `).join("");
  // fetch fire risks for labels
  fetch("/api/risk").then(r => r.json()).then(risks => {
    risks.forEach(r => {
      const el = document.getElementById(`zone-risk-${r.zone_id}`);
      if (el) {
        const levelColors = {low:"#2ecc71",medium:"#f1c40f",high:"#e67e22",critical:"#e74c3c"};
        el.style.color = levelColors[r.risk_level] || "#8fa3b3";
        el.textContent = `🔥 ${r.risk_score}/100 (${r.risk_level})`;
      }
    });
  }).catch(() => {});
}

function populatePlannerZoneSelect(zones) {
  const sel = document.getElementById("planner-zone");
  sel.innerHTML = zones.map(z => `<option value="${z.id}">${z.name}</option>`).join("");
  const d = new Date().toISOString().split("T")[0];
  document.getElementById("planner-date").value = d;
  document.getElementById("planner-date").min = d;
}

// ─── Global Banner ────────────────────────────────────────────────────────────
async function refreshGlobalBanner() {
  try {
    const res = await fetch("/api/agents/status");
    const data = await res.json();
    const banner = document.getElementById("global-banner");
    const unsafe = data.zones.filter(z => !z.overall_safe).length;
    const total  = data.zones.length;
    if (unsafe === 0) {
      banner.className = "global-status-banner all-clear";
      banner.innerHTML = `✅ Tunisia is clear today — all ${total} zones safe`;
    } else if (unsafe <= 2) {
      banner.className = "global-status-banner caution";
      banner.innerHTML = `⚠️ ${unsafe} zone${unsafe>1?"s":""} with elevated risk — check before travel`;
    } else {
      banner.className = "global-status-banner alerts-active";
      banner.innerHTML = `🔥 ${unsafe} zones with active alerts — multi-agent analysis running`;
    }
  } catch {
    document.getElementById("global-banner").innerHTML = "🌐 Multi-agent platform online";
  }
}

// ─── Zone Selection ───────────────────────────────────────────────────────────
async function selectZone(zoneId) {
  if (currentZone === zoneId) return;
  currentZone = zoneId;

  // Update zone btn styles
  document.querySelectorAll(".zone-btn").forEach(b => b.classList.remove("active"));
  const btn = document.getElementById(`zone-btn-${zoneId}`);
  if (btn) btn.classList.add("active");

  // Show dashboard with loading skeleton
  document.getElementById("zone-dashboard").style.display = "block";
  showDashboardSkeleton();

  try {
    dashboardData = await fetch(`/api/tourist/dashboard/${zoneId}`).then(r => r.json());
    allNotifications = dashboardData.notifications || [];
    renderDashboard(dashboardData);
  } catch (err) {
    console.error("Dashboard load failed:", err);
  }
}

function showDashboardSkeleton() {
  document.getElementById("overall-val").textContent = "…";
  document.getElementById("summary-title").textContent = "Loading…";
  document.getElementById("summary-desc").textContent  = "Running all 7 agents…";
  document.getElementById("agent-cards-grid").innerHTML = Array(6).fill(
    `<div class="skeleton" style="height:140px;border-radius:12px;"></div>`
  ).join("");
}

// ─── Render Dashboard ─────────────────────────────────────────────────────────
function renderDashboard(data) {
  renderScoreRing(data.overall_safety_score);
  renderSummary(data);
  renderAgentCards(data.agent_cards);
  renderDestinations(data.tourism);
  renderAlerts(allNotifications);
  renderXai(data);
  updateMapWithRisks(data);
}

function renderScoreRing(score) {
  const ring = document.getElementById("score-ring");
  const val  = document.getElementById("overall-val");
  val.textContent = Math.round(score);
  const color = score >= 75 ? "#2ecc71" : score >= 50 ? "#f1c40f" : score >= 30 ? "#e67e22" : "#e74c3c";
  ring.style.background = `conic-gradient(${color} ${score}%, var(--bg-surface) 0%)`;
  val.style.color = color;
}

function renderSummary(data) {
  const title = document.getElementById("summary-title");
  const desc  = document.getElementById("summary-desc");
  const badge = document.getElementById("notif-badge");

  const score = data.overall_safety_score;
  const zname = data.zone_name;

  if (score >= 75) {
    title.textContent = `${zname} — Great time to visit!`;
    desc.textContent  = data.tourism?.top_recommendation || "All conditions are favorable for tourism.";
  } else if (score >= 50) {
    title.textContent = `${zname} — Visit with caution`;
    desc.textContent  = data.tourism?.top_recommendation || "Some agents report elevated risk. Check alerts.";
  } else {
    title.textContent = `${zname} — Exercise caution`;
    desc.textContent  = data.tourism?.top_recommendation || "Multiple agents report active hazards. Consider alternatives.";
  }

  const criticals = data.notifications?.filter(n => n.severity === "critical").length || 0;
  if (criticals > 0) {
    badge.innerHTML = `<div class="notif-counter"><span class="notif-dot"></span> ${criticals} critical alert${criticals>1?"s":""}</div>`;
  } else {
    badge.innerHTML = "";
  }
}

function renderAgentCards(cards) {
  const grid = document.getElementById("agent-cards-grid");
  grid.innerHTML = cards.map(card => `
    <div class="portal-agent-card" onclick="switchTab('agents')" title="${card.agent_name}">
      <div class="card-glow ${card.risk_level}"></div>
      <div class="portal-agent-icon">${card.icon}</div>
      <div class="portal-agent-name">${card.agent_name}</div>
      <div class="portal-agent-score ${card.risk_level}">${Math.round(card.risk_score)}</div>
      <div class="portal-agent-label">${card.status_label}</div>
      <div class="portal-agent-metric">${card.key_metric}</div>
      ${card.is_simulated ? '<div style="font-size:10px;color:var(--text-muted);margin-top:6px;opacity:0.6;">⚙ Simulated data</div>' : '<div style="font-size:10px;color:var(--cyan);margin-top:6px;">🛰 Live data</div>'}
    </div>
  `).join("");
}

// ─── Destinations ─────────────────────────────────────────────────────────────
function renderDestinations(tourism) {
  if (!tourism) return;

  // Festivals
  const festivals = tourism.active_festivals || [];
  const festRow   = document.getElementById("festivals-row");
  const festList  = document.getElementById("festivals-list");
  if (festivals.length > 0) {
    festRow.style.display = "block";
    festList.innerHTML = festivals.map(f => `
      <div class="festival-card">
        <div class="festival-icon">🎭</div>
        <div>
          <div class="festival-name">${f.name}</div>
          <div class="festival-meta">${f.type} · This month</div>
        </div>
      </div>
    `).join("");
  } else {
    festRow.style.display = "none";
  }

  const dests   = tourism.recommended_destinations || [];
  const grid    = document.getElementById("dest-grid");
  const noEl    = document.getElementById("no-destinations");
  const subtitle= document.getElementById("dest-subtitle");

  subtitle.textContent = `${dests.length} destination${dests.length !== 1 ? "s" : ""} · Safety score: ${tourism.overall_safety_score}/100`;

  if (dests.length === 0) {
    grid.innerHTML = "";
    noEl.style.display = "block";
  } else {
    noEl.style.display = "none";
    grid.innerHTML = dests.map(d => `
      <div class="destination-card">
        <div class="dest-image">
          ${DEST_EMOJI[d.type] || "📍"}
          <div class="dest-safety-tag ${d.safety_tag}">${d.safety_tag === "safe" ? "✓ Safe" : d.safety_tag === "caution" ? "⚠ Caution" : "✗ Avoid"}</div>
        </div>
        <div class="dest-body">
          <div class="dest-name">${d.name}</div>
          <div class="dest-type">${d.type.replace("_", " ")}</div>
          <div class="dest-description">${d.description}</div>
          <div class="dest-activities">
            ${(d.activities || []).slice(0, 4).map(a => `<span class="activity-tag">${a}</span>`).join("")}
          </div>
          <div class="dest-amenities">
            <span>🏨 ${d.amenities?.hotels ?? 0} hotels</span>
            <span>🍽 ${d.amenities?.restaurants ?? 0} restaurants</span>
            ${d.amenities?.hospitals > 0 ? `<span>🏥 ${d.amenities.hospitals} hospital${d.amenities.hospitals > 1 ? "s" : ""}</span>` : ""}
          </div>
        </div>
      </div>
    `).join("");
  }

  // Routing
  const routing  = tourism.smart_routing || [];
  const routeEl  = document.getElementById("routing-list");
  if (routing.length > 0) {
    routeEl.innerHTML = routing.map(r => `
      <div class="routing-card">
        <div class="routing-label">✅ Recommended Route</div>
        <div class="routing-route">${r.recommended_route}</div>
        <div class="routing-reason">${r.reason}</div>
        <div class="routing-meta">
          <span>📍 ${r.from} → ${r.to}</span>
          ${r.extra_time_min ? `<span>⏱ +${r.extra_time_min} min</span>` : ""}
          <span>Confidence: ${r.confidence}</span>
        </div>
      </div>
    `).join("");
  } else {
    routeEl.innerHTML = `
      <div class="empty-state" style="padding:24px;">
        <div class="empty-state-icon">🛣️</div>
        <p>No route advisories for current conditions.<br>All main roads are clear.</p>
      </div>`;
  }
}

// ─── Global Destinations ──────────────────────────────────────────────────────
async function loadGlobalDestinations() {
  try {
    const res = await fetch("/api/agents/status");
    const data = await res.json();
    const grid = document.getElementById("global-dest-grid");

    // We'll load tourism for a few safe zones
    const safeZones = data.zones.filter(z => z.overall_safe).slice(0, 4);
    if (safeZones.length === 0) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><div class="empty-state-icon">⚠️</div><p>All zones have elevated risk today. Plan travel carefully.</p></div>`;
      return;
    }

    const tourismResults = await Promise.allSettled(
      safeZones.map(z => fetch(`/api/agents/tourism/${z.zone_id}`).then(r => r.json()))
    );

    const cards = [];
    safeZones.forEach((z, i) => {
      const result = tourismResults[i];
      if (result.status !== "fulfilled") return;
      const tourism = result.value;
      const dests = tourism.recommended_destinations || [];
      const topDest = dests[0];
      if (!topDest) return;
      cards.push(`
        <div class="destination-card" onclick="selectZone('${z.zone_id}')">
          <div class="dest-image">
            ${DEST_EMOJI[topDest.type] || "📍"}
            <div class="dest-safety-tag safe">✓ Safe</div>
          </div>
          <div class="dest-body">
            <div class="dest-name">${topDest.name}</div>
            <div class="dest-type">${topDest.type.replace("_"," ")}</div>
            <div class="dest-description">${topDest.description}</div>
            <div class="dest-activities">
              ${(topDest.activities||[]).slice(0,3).map(a=>`<span class="activity-tag">${a}</span>`).join("")}
            </div>
            <div class="dest-amenities">
              <span>🏨 ${topDest.amenities?.hotels ?? 0} hotels</span>
              <span>Safety: <strong style="color:var(--green)">${tourism.overall_safety_score}/100</strong></span>
            </div>
          </div>
        </div>
      `);
    });

    grid.innerHTML = cards.length > 0 ? cards.join("") :
      `<div class="empty-state" style="grid-column:1/-1;"><p>Loading safe destinations…</p></div>`;
  } catch (err) {
    console.error("Global destinations failed:", err);
  }
}

// ─── Alerts ───────────────────────────────────────────────────────────────────
function renderAlerts(notifications, filter = "all") {
  const list = document.getElementById("alerts-list");
  const filtered = filter === "all" ? notifications : notifications.filter(n => n.stakeholder === filter);

  if (filtered.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">✅</div>
        <p>No alerts for this filter. ${filter !== "all" ? "Try 'All'." : ""}</p>
      </div>`;
    return;
  }

  list.innerHTML = filtered.map(n => `
    <div class="alert-item ${n.severity}">
      <div class="alert-icon">${n.icon}</div>
      <div class="alert-body">
        <div class="alert-title">${n.title}</div>
        <div class="alert-message">${n.message}</div>
        <div class="alert-actions">
          ${(n.actions || []).map(a => `<span class="alert-action-tag">→ ${a}</span>`).join("")}
        </div>
      </div>
      <div class="alert-meta">
        <div class="alert-stakeholder">${n.stakeholder.replace("_"," ")}</div>
        <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">${n.agent_source}</div>
      </div>
    </div>
  `).join("");
}

function setupAlertsFilter() {
  document.getElementById("alerts-filter-bar").addEventListener("click", e => {
    const btn = e.target.closest("[data-filter]");
    if (!btn) return;
    document.querySelectorAll("#alerts-filter-bar [data-filter]").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    renderAlerts(allNotifications, btn.dataset.filter);
  });
}

// ─── XAI Panel ────────────────────────────────────────────────────────────────
function renderXai(data) {
  renderXaiForAgent("fire");
}

function setupXaiSelector() {
  document.getElementById("xai-agent-selector").addEventListener("change", e => {
    if (currentZone) renderXaiForAgent(e.target.value);
  });
}

async function renderXaiForAgent(agentType) {
  if (!currentZone) return;
  const container = document.getElementById("xai-content");
  container.innerHTML = `<div style="padding:32px;text-align:center;"><div class="spinner"></div><div style="margin-top:12px;color:var(--text-muted);font-size:13px;">Loading XAI analysis…</div></div>`;

  try {
    const xai = await fetch(`/api/agents/xai/${agentType}/${currentZone}`).then(r => r.json());
    const scoreColor = xai.risk_level === "low" ? "var(--risk-low)" : xai.risk_level === "medium" ? "var(--risk-medium)" : xai.risk_level === "high" ? "var(--risk-high)" : "var(--risk-critical)";

    container.innerHTML = `
      <div class="xai-panel">
        <div class="xai-panel-header">
          🔍 ${xai.agent} — Explainability Report
        </div>
        <div style="margin-bottom:16px;">
          <div style="font-size:20px;font-weight:900;color:${scoreColor};">${xai.prediction}</div>
          <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;line-height:1.5;">${xai.plain_language}</div>
        </div>

        <div style="margin-bottom:16px;">
          <div style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;">Factor Breakdown</div>
          <ul class="xai-factor-list">
            ${(xai.factors_breakdown || []).map(f => {
              const contribPct = f.contribution === "critical" ? 100 : f.contribution === "high" ? 75 : f.contribution === "medium" ? 45 : 15;
              return `
                <li class="xai-factor">
                  <span class="factor-name">${f.factor}</span>
                  <div class="factor-bar-wrap"><div class="factor-bar ${f.contribution}" style="width:${contribPct}%"></div></div>
                  <span class="factor-value">${f.value}</span>
                  <span style="font-size:11px;color:var(--text-muted);min-width:140px;text-align:right;">${f.direction}</span>
                </li>`;
            }).join("")}
          </ul>
        </div>

        <div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;margin-bottom:12px;">
          <div style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;">Historical Context</div>
          <div style="font-size:13px;color:var(--text-secondary);line-height:1.5;">${xai.historical_context}</div>
        </div>

        <div style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:6px;">
          ⚙ ${xai.confidence_note}
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><p>XAI analysis unavailable.</p></div>`;
  }
}

// ─── Trip Planner ─────────────────────────────────────────────────────────────
function setupPlannerForm() {
  document.getElementById("planner-submit").addEventListener("click", runPlannerAnalysis);
}

async function runPlannerAnalysis() {
  const zoneId = document.getElementById("planner-zone").value;
  const date   = document.getElementById("planner-date").value;
  const btn    = document.getElementById("planner-submit");
  const report = document.getElementById("planner-report");

  if (!zoneId || !date) return;

  btn.disabled    = true;
  btn.textContent = "⏳ Analyzing…";
  report.classList.remove("visible");

  try {
    // Run tourist query + dashboard in parallel
    const [touristRes, dashRes, tourismRes] = await Promise.all([
      fetch("/api/tourist/query", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ zone_id: zoneId, visit_date: date, lang: "en" }),
      }).then(r => r.json()),
      fetch(`/api/tourist/dashboard/${zoneId}`).then(r => r.json()),
      fetch(`/api/agents/tourism/${zoneId}`).then(r => r.json()),
    ]);

    // Score ring
    const scoreEl = document.getElementById("report-score");
    const ringEl  = document.getElementById("report-ring");
    scoreEl.textContent = touristRes.risk_score;
    const sc = touristRes.risk_score;
    const rcol = sc < 30 ? "#2ecc71" : sc < 50 ? "#f1c40f" : sc < 70 ? "#e67e22" : "#e74c3c";
    ringEl.style.background = `conic-gradient(${rcol} ${sc}%, var(--bg-surface) 0%)`;
    scoreEl.style.color = rcol;

    document.getElementById("report-title").textContent =
      `${touristRes.zone_name} — ${touristRes.safe ? "✅ Safe to Visit" : "⚠️ Elevated Risk"}`;
    document.getElementById("report-date-note").textContent =
      `${touristRes.forecast_used ? "📅 Forecast for" : "📅 Based on conditions from"} ${touristRes.effective_date}`;

    // Agent rows
    const agentRowsEl = document.getElementById("report-agents");
    agentRowsEl.innerHTML = dashRes.agent_cards.map(c => {
      const col = c.risk_level === "low" ? "var(--risk-low)" : c.risk_level === "medium" ? "var(--risk-medium)" : c.risk_level === "high" ? "var(--risk-high)" : "var(--risk-critical)";
      return `
        <div class="mini-agent-row">
          <span>${c.icon} ${c.agent_name}</span>
          <span style="color:${col};font-weight:700;">${Math.round(c.risk_score)}/100 · ${c.status_label}</span>
        </div>`;
    }).join("");

    // Explanation
    document.getElementById("report-explanation").textContent = touristRes.explanation;
    document.getElementById("report-alternative").textContent =
      touristRes.alternative_zone_name
        ? `✅ Alternative recommended: ${touristRes.alternative_zone_name} (lower risk)`
        : "";

    // Routing
    const routing = tourismRes.smart_routing || [];
    const rSection = document.getElementById("report-routing-section");
    const rList    = document.getElementById("report-routing-list");
    if (routing.length > 0) {
      rSection.style.display = "block";
      rList.innerHTML = routing.map(r => `
        <div class="routing-card">
          <div class="routing-label">✅ Recommended</div>
          <div class="routing-route">${r.recommended_route}</div>
          <div class="routing-reason">${r.reason}</div>
          <div class="routing-meta"><span>📍 ${r.from} → ${r.to}</span>${r.extra_time_min?`<span>⏱ +${r.extra_time_min} min</span>`:""}</div>
        </div>
      `).join("");
    } else {
      rSection.style.display = "none";
    }

    // Alerts
    const alertsEl = document.getElementById("report-alerts");
    const touristAlerts = dashRes.notifications?.filter(n => n.stakeholder === "tourist") || [];
    if (touristAlerts.length === 0) {
      alertsEl.innerHTML = `<div style="color:var(--text-muted);font-size:13px;">✅ No tourist alerts for this zone.</div>`;
    } else {
      alertsEl.innerHTML = touristAlerts.map(n => `
        <div class="alert-item ${n.severity}" style="margin-bottom:8px;">
          <div class="alert-icon">${n.icon}</div>
          <div class="alert-body">
            <div class="alert-title">${n.title}</div>
            <div class="alert-message">${n.message}</div>
          </div>
        </div>
      `).join("");
    }

    report.classList.add("visible");
  } catch (err) {
    console.error("Planner analysis failed:", err);
  } finally {
    btn.disabled    = false;
    btn.textContent = "Analyze →";
  }
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll(".tab-btn[data-tab]").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn[data-tab]").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  if (btn) btn.classList.add("active");
  const panel = document.getElementById(`tab-${tabId}`);
  if (panel) panel.classList.add("active");

  // Load XAI when switching to XAI tab
  if (tabId === "xai" && currentZone) {
    const sel = document.getElementById("xai-agent-selector").value;
    renderXaiForAgent(sel);
  }
}

// ─── Leaflet Map ──────────────────────────────────────────────────────────────
function initMap() {
  if (map) return;
  map = L.map("portal-map").setView([34.0, 9.0], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);
}

function updateMapWithRisks(data) {
  if (!map) return;
  const levelColors = { low:"#2ecc71", medium:"#f1c40f", high:"#e67e22", critical:"#e74c3c" };

  // Show current zone risk
  const fireScore = data.fire?.risk_score || 0;
  const level = data.fire?.risk_level || "low";
  const color = levelColors[level] || "#7fd0ff";

  const zone = allZones.find(z => z.id === data.zone_id);
  if (!zone) return;

  // Remove old markers
  Object.values(markers).forEach(m => m.remove());
  markers = {};

  // Add marker for selected zone
  const m = L.circleMarker([zone.lat, zone.lon], {
    radius: 18,
    color,
    fillColor: color,
    fillOpacity: 0.8,
    weight: 3,
  }).addTo(map).bindPopup(`
    <strong>${zone.name}</strong><br>
    🔥 Fire: ${fireScore}/100 (${level})<br>
    🌊 Flood: ${data.flood?.flood_probability?.toFixed(0) || "N/A"}/100<br>
    💧 Water: ${data.water?.shortage_probability?.toFixed(0) || "N/A"}/100<br>
    ⚡ Electricity: ${data.electricity?.outage_probability?.toFixed(0) || "N/A"}/100<br>
    🗺 Safety: ${data.overall_safety_score?.toFixed(0) || "N/A"}/100
  `).openPopup();
  markers[zone.id] = m;
  map.setView([zone.lat, zone.lon], 9);

  // Also show all zones
  fetch("/api/risk").then(r => r.json()).then(risks => {
    risks.forEach(r => {
      if (r.zone_id === data.zone_id) return;
      const z = allZones.find(z => z.id === r.zone_id);
      if (!z) return;
      const rc = levelColors[r.risk_level] || "#7fd0ff";
      const mk = L.circleMarker([z.lat, z.lon], {
        radius: 10, color: rc, fillColor: rc, fillOpacity: 0.6, weight: 2,
      }).addTo(map).bindPopup(`<strong>${z.name}</strong><br>Fire risk: ${r.risk_score}/100`);
      mk.on("click", () => selectZone(z.id));
      markers[z.id] = mk;
    });
  }).catch(() => {});
}
