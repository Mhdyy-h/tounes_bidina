/**
 * Dashboard JS — Tunisia Guardian AI Multi-Agent Operations Dashboard
 * Loads: fire risk table, flood/water/electricity agent data, agent health overview
 */

const LEVEL_COLORS = {
  low:      "#2ecc71",
  medium:   "#f1c40f",
  high:     "#e67e22",
  critical: "#e74c3c",
};

const AGENT_DEFS = [
  { key: "fire",        icon: "🔥", name: "Fire Intelligence",          desc: "Wildfire ML · NDVI · FIRMS" },
  { key: "flood",       icon: "🌊", name: "Flood Intelligence",          desc: "Rainfall · Terrain · Drainage" },
  { key: "water",       icon: "💧", name: "Water Resources",             desc: "Reservoir · Tourism demand · Leaks" },
  { key: "electricity", icon: "⚡", name: "Electricity & Infrastructure", desc: "Grid · Solar · Hotel backup" },
  { key: "tourism",     icon: "🗺️", name: "Tourism Intelligence",        desc: "Destinations · Routing · Festivals" },
  { key: "emergency",   icon: "🚨", name: "Emergency Optimization",       desc: "Firefighters · Ambulances · Helicopters" },
];

let zoneRisks   = [];
let agentSummary = {};

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await Promise.all([loadFireRisks(), loadNdviStatus()]);
  renderAgentOverview();
}

// ─── Fire Risks ───────────────────────────────────────────────────────────────
async function loadFireRisks() {
  try {
    const res  = await fetch("/api/risk");
    zoneRisks  = await res.json();

    const total    = zoneRisks.length;
    const critical = zoneRisks.filter(z => z.risk_level === "critical").length;
    const high     = zoneRisks.filter(z => z.risk_level === "high").length;
    const avg      = Math.round(zoneRisks.reduce((s, z) => s + z.risk_score, 0) / (total || 1));

    document.getElementById("stat-total").textContent    = total;
    document.getElementById("stat-critical").textContent = critical;
    document.getElementById("stat-high").textContent     = high;
    document.getElementById("stat-avg").textContent      = avg;
    document.getElementById("last-update").textContent   = new Date().toLocaleTimeString();

    // Fire summary for agent overview
    const maxFire = zoneRisks.reduce((m, z) => z.risk_score > m.score ? {score: z.risk_score, level: z.risk_level} : m, {score: 0, level: "low"});
    agentSummary["fire"] = { score: maxFire.score, level: maxFire.level, metric: `Max zone: ${maxFire.score}/100` };

    renderZoneTable();
    await loadSecondaryAgents();
  } catch (err) {
    console.error("Fire risk load failed:", err);
    document.getElementById("dashboard-body").innerHTML =
      `<tr><td colspan="10" class="loading-row">Error loading data — is the server running?</td></tr>`;
  }
}

// ─── Secondary Agents (sample first zone) ────────────────────────────────────
async function loadSecondaryAgents() {
  if (zoneRisks.length === 0) return;

  // Sample highest-risk zone for agent overview
  const topZone = zoneRisks.reduce((m, z) => z.risk_score > m.risk_score ? z : m, zoneRisks[0]);

  try {
    const [flood, water, elec, tourism, emergency] = await Promise.allSettled([
      fetch(`/api/agents/flood/${topZone.zone_id}`).then(r => r.json()),
      fetch(`/api/agents/water/${topZone.zone_id}`).then(r => r.json()),
      fetch(`/api/agents/electricity/${topZone.zone_id}`).then(r => r.json()),
      fetch(`/api/agents/tourism/${topZone.zone_id}`).then(r => r.json()),
      fetch(`/api/agents/emergency/${topZone.zone_id}`).then(r => r.json()),
    ]);

    if (flood.status === "fulfilled") {
      const d = flood.value;
      agentSummary["flood"] = {score: d.flood_probability, level: d.risk_level, metric: `${d.flood_probability.toFixed(0)}/100 probability`};
    }
    if (water.status === "fulfilled") {
      const d = water.value;
      agentSummary["water"] = {score: d.shortage_probability, level: d.risk_level, metric: `${d.factors.reservoir_level_pct.toFixed(0)}% reservoir avg`};
    }
    if (elec.status === "fulfilled") {
      const d = elec.value;
      agentSummary["electricity"] = {score: d.outage_probability, level: d.risk_level, metric: `${d.hotel_availability_pct.toFixed(0)}% hotels powered`};
    }
    if (tourism.status === "fulfilled") {
      const d = tourism.value;
      agentSummary["tourism"] = {score: 100 - d.overall_safety_score, level: d.overall_safety_score >= 75 ? "low" : d.overall_safety_score >= 50 ? "medium" : "high", metric: `Safety: ${d.overall_safety_score.toFixed(0)}/100`};
    }
    if (emergency.status === "fulfilled") {
      const d = emergency.value;
      agentSummary["emergency"] = {score: d.priority_score, level: d.overall_priority, metric: `Priority: ${d.overall_priority.toUpperCase()}`};
    }

    renderAgentOverview();
    await enrichTableWithSecondaryData(topZone.zone_id);
  } catch (err) {
    console.error("Secondary agents failed:", err);
  }
}

// ─── Zone Table ───────────────────────────────────────────────────────────────
function renderZoneTable() {
  const body = document.getElementById("dashboard-body");
  if (zoneRisks.length === 0) {
    body.innerHTML = `<tr><td colspan="10" class="loading-row">No zone data available.</td></tr>`;
    return;
  }

  const sorted = [...zoneRisks].sort((a, b) => b.risk_score - a.risk_score);
  body.innerHTML = sorted.map(zone => {
    const color = LEVEL_COLORS[zone.risk_level] || "#7fd0ff";
    const conf  = 100 - zone.risk_score;
    const time  = new Date(zone.updated_at).toLocaleTimeString();
    return `
      <tr id="row-${zone.zone_id}">
        <td style="font-weight:600">${zone.zone_name}</td>
        <td style="font-weight:700;color:${color}">${zone.risk_score}/100</td>
        <td><span class="level-pill" style="background:${color}22;color:${color}">${zone.risk_level}</span></td>
        <td id="flood-${zone.zone_id}" style="color:var(--text-muted)">–</td>
        <td id="water-${zone.zone_id}" style="color:var(--text-muted)">–</td>
        <td id="elec-${zone.zone_id}"  style="color:var(--text-muted)">–</td>
        <td>${zone.factors.temperature_c.toFixed(1)} °C</td>
        <td>${zone.factors.wind_kmh.toFixed(1)} km/h</td>
        <td>${zone.factors.humidity_pct.toFixed(0)} %</td>
        <td style="color:var(--text-muted);font-size:11px">${time}</td>
      </tr>`;
  }).join("");
}

async function enrichTableWithSecondaryData(priorityZoneId) {
  // Enrich all zones with flood/water/elec data (in small batches to avoid hammering the server)
  const zones = [...zoneRisks].sort((a, b) => b.risk_score - a.risk_score);

  for (const zone of zones) {
    try {
      const [flood, water, elec] = await Promise.allSettled([
        fetch(`/api/agents/flood/${zone.zone_id}`).then(r => r.json()),
        fetch(`/api/agents/water/${zone.zone_id}`).then(r => r.json()),
        fetch(`/api/agents/electricity/${zone.zone_id}`).then(r => r.json()),
      ]);

      if (flood.status === "fulfilled") {
        const el = document.getElementById(`flood-${zone.zone_id}`);
        if (el) {
          const d = flood.value;
          const col = LEVEL_COLORS[d.risk_level] || "#8fa3b3";
          el.style.color = col;
          el.textContent = `${d.flood_probability.toFixed(0)}/100`;
        }
      }
      if (water.status === "fulfilled") {
        const el = document.getElementById(`water-${zone.zone_id}`);
        if (el) {
          const d = water.value;
          const col = LEVEL_COLORS[d.risk_level] || "#8fa3b3";
          el.style.color = col;
          el.textContent = `${d.shortage_probability.toFixed(0)}/100`;
        }
      }
      if (elec.status === "fulfilled") {
        const el = document.getElementById(`elec-${zone.zone_id}`);
        if (el) {
          const d = elec.value;
          const col = LEVEL_COLORS[d.risk_level] || "#8fa3b3";
          el.style.color = col;
          el.textContent = `${d.outage_probability.toFixed(0)}/100`;
        }
      }
    } catch (_) { /* silently skip */ }

    // Small pause between zones to avoid overwhelming the server
    await new Promise(r => setTimeout(r, 150));
  }
}

// ─── Agent Overview ───────────────────────────────────────────────────────────
function renderAgentOverview() {
  const grid = document.getElementById("agent-overview-grid");
  grid.innerHTML = AGENT_DEFS.map(agent => {
    const summary  = agentSummary[agent.key] || {score: 0, level: "low", metric: "Loading…"};
    const color    = LEVEL_COLORS[summary.level] || "#7fd0ff";
    const labels   = {low:"All Clear",medium:"Watch",high:"Warning",critical:"Critical"};
    const statusLbl= labels[summary.level] || "Unknown";
    return `
      <div class="agent-card risk-${summary.level}">
        <div class="agent-icon">${agent.icon}</div>
        <div class="agent-name">${agent.name}</div>
        <div class="agent-status ${summary.level}">${statusLbl}</div>
        <div class="agent-metric">${summary.metric}</div>
        <div style="font-size:10px;color:var(--text-muted);margin-top:6px;">${agent.desc}</div>
      </div>`;
  }).join("");
}

// ─── NDVI Status ──────────────────────────────────────────────────────────────
async function loadNdviStatus() {
  try {
    const res    = await fetch("/api/ndvi/status");
    const status = await res.json();
    const realCount = (status.zones || []).filter(z => z.is_real).length;
    const total     = (status.zones || []).length;
    document.getElementById("stat-ndvi").textContent = `${realCount}/${total}`;
  } catch {
    document.getElementById("stat-ndvi").textContent = "–";
  }
}

// ─── Auto-refresh ─────────────────────────────────────────────────────────────
init();
setInterval(async () => {
  await loadFireRisks();
}, 30000);
