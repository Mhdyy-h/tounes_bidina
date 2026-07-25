const touristId = getTouristId();

const balanceEl = document.getElementById("rw-balance");
const earnedEl = document.getElementById("rw-earned");
const spentEl = document.getElementById("rw-spent");
const zoneFilterEl = document.getElementById("rw-zone-filter");
const catalogEl = document.getElementById("rw-catalog");
const historyBodyEl = document.getElementById("rw-history-body");
const modalBackdrop = document.getElementById("rw-modal-backdrop");

let checkpointNameById = {};
let currentBalance = 0;

async function loadZonesFilter() {
  const res = await fetch("/api/zones");
  const zones = await res.json();
  zoneFilterEl.innerHTML =
    `<option value="">${t("rewardsZoneAll")}</option>` +
    zones.map((z) => `<option value="${z.id}">${z.name}</option>`).join("");
}

async function loadCheckpointNames() {
  const res = await fetch("/api/rewards/checkpoints");
  const checkpoints = await res.json();
  checkpointNameById = Object.fromEntries(checkpoints.map((c) => [c.id, c.name]));
}

async function loadBalance() {
  const res = await fetch(`/api/rewards/balance/${encodeURIComponent(touristId)}`);
  const data = await res.json();
  currentBalance = data.balance;
  balanceEl.textContent = data.balance;
  earnedEl.textContent = data.total_earned;
  spentEl.textContent = data.total_spent;
  renderHistory(data.recent_transactions);
  renderCatalog(); // re-render so redeem buttons reflect the fresh balance
}

function renderHistory(transactions) {
  if (!transactions.length) {
    historyBodyEl.innerHTML = `<tr><td colspan="3" class="loading-row">${t("rewardsNoHistory")}</td></tr>`;
    return;
  }
  historyBodyEl.innerHTML = transactions
    .map((tx) => {
      const name = checkpointNameById[tx.checkpoint_id] || tx.checkpoint_id;
      const date = new Date(tx.earned_at).toLocaleString();
      return `<tr><td>${name}</td><td>+${tx.points}</td><td>${date}</td></tr>`;
    })
    .join("");
}

let catalogCache = [];

async function loadCatalog() {
  const zoneId = zoneFilterEl.value;
  const url = zoneId ? `/api/rewards/catalog?zone_id=${encodeURIComponent(zoneId)}` : "/api/rewards/catalog";
  const res = await fetch(url);
  catalogCache = await res.json();
  renderCatalog();
}

function renderCatalog() {
  if (!catalogCache.length) {
    catalogEl.innerHTML = `<p class="hint">${t("rewardsNoRewards")}</p>`;
    return;
  }
  catalogEl.innerHTML = catalogCache
    .map((r) => {
      const canAfford = currentBalance >= r.points_cost;
      return `
      <div class="reward-card">
        <div class="reward-card-title">${r.title}</div>
        <div class="reward-card-partner">${r.partner_name}</div>
        <div class="reward-card-desc">${r.description || ""}</div>
        <div class="reward-card-cost">${r.points_cost} pts</div>
        <button class="reward-card-redeem" data-reward-id="${r.id}" ${canAfford ? "" : "disabled"}>
          ${canAfford ? t("rewardsRedeemBtn") : t("rewardsRedeemDisabled")}
        </button>
      </div>`;
    })
    .join("");

  catalogEl.querySelectorAll(".reward-card-redeem").forEach((btn) => {
    btn.addEventListener("click", () => redeemReward(btn.dataset.rewardId, btn));
  });
}

function showRedeemModal(ok, message, code) {
  document.getElementById("rw-modal-title").textContent = ok
    ? t("rewardsCodeTitle")
    : t("rewardsRedeemFailedTitle");
  document.getElementById("rw-modal-message").textContent = message;

  const codeEl = document.getElementById("rw-modal-code");
  const hintEl = document.getElementById("rw-modal-hint");
  codeEl.textContent = ok ? code : "";
  codeEl.style.display = ok ? "block" : "none";
  hintEl.style.display = ok ? "block" : "none";

  modalBackdrop.classList.add("open");
}

async function redeemReward(rewardId, btn) {
  btn.disabled = true;
  try {
    const res = await fetch("/api/rewards/redeem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tourist_id: touristId, reward_id: rewardId }),
    });
    const data = await res.json();
    showRedeemModal(data.ok, data.reason, data.redemption_code);
    if (data.ok) {
      await loadBalance();
    } else {
      btn.disabled = false;
    }
  } catch (err) {
    showRedeemModal(false, err.message, null);
    btn.disabled = false;
  }
}

document.getElementById("rw-modal-close").addEventListener("click", () => {
  modalBackdrop.classList.remove("open");
});
modalBackdrop.addEventListener("click", (e) => {
  if (e.target === modalBackdrop) modalBackdrop.classList.remove("open");
});

zoneFilterEl.addEventListener("change", loadCatalog);
document.addEventListener("langchange", () => {
  loadZonesFilter();
  renderCatalog();
});

async function init() {
  await Promise.all([loadZonesFilter(), loadCheckpointNames()]);
  await loadCatalog();
  await loadBalance();
}

document.addEventListener("DOMContentLoaded", init);
