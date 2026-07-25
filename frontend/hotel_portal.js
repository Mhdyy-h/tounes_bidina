const zoneSelect = document.getElementById("zone");
const form = document.getElementById("hotel-form");
const resultBox = document.getElementById("result");
const confirmMsg = document.getElementById("confirm-msg");
const tableBody = document.getElementById("hotel-table-body");

async function loadZones() {
  const res = await fetch("/api/zones");
  const zones = await res.json();
  zoneSelect.innerHTML = zones.map((z) => `<option value="${z.id}">${z.name}</option>`).join("");
  await refreshHotelTable();
}

async function refreshHotelTable() {
  const zoneId = zoneSelect.value;
  if (!zoneId) return;
  tableBody.innerHTML = `<tr><td colspan="9" class="loading-row">Loading…</td></tr>`;
  try {
    const res = await fetch(`/api/hotels/${zoneId}`);
    const hotels = await res.json();
    if (hotels.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="9" class="loading-row">No hotels declared yet in this zone.</td></tr>`;
      return;
    }
    const check = (v) => (v ? "✅" : "❌");
    tableBody.innerHTML = hotels
      .map(
        (h) => `
      <tr>
        <td>${h.hotel_name}</td>
        <td>${check(h.electricity_available)}</td>
        <td>${check(h.water_available)}</td>
        <td>${check(h.internet_available)}</td>
        <td>${check(h.generator_available)}</td>
        <td>${check(h.battery_backup)}</td>
        <td>${check(h.solar_panels)}</td>
        <td>${h.rooms_available ?? "–"}</td>
        <td>${new Date(h.updated_at).toLocaleTimeString()}</td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="9" class="loading-row">Failed to load.</td></tr>`;
  }
}

zoneSelect.addEventListener("change", refreshHotelTable);

const submitBtn = form.querySelector(".btn-submit");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const originalLabel = submitBtn.textContent;
  submitBtn.disabled = true;
  submitBtn.textContent = "⏳ Submitting…";

  try {
    const body = {
      zone_id: zoneSelect.value,
      hotel_name: document.getElementById("hotel-name").value,
      electricity_available: document.getElementById("electricity").checked,
      water_available: document.getElementById("water").checked,
      internet_available: document.getElementById("internet").checked,
      generator_available: document.getElementById("generator").checked,
      battery_backup: document.getElementById("battery").checked,
      solar_panels: document.getElementById("solar").checked,
      remaining_autonomy_hours: document.getElementById("autonomy").value
        ? parseFloat(document.getElementById("autonomy").value)
        : null,
      rooms_available: document.getElementById("rooms").value
        ? parseInt(document.getElementById("rooms").value, 10)
        : null,
      contact_email: document.getElementById("email").value || null,
    };

    const res = await fetch("/api/hotels/declare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("Request failed");
    const data = await res.json();

    resultBox.style.display = "block";
    resultBox.className = "result safe";
    confirmMsg.textContent = `✅ Status saved for "${data.hotel_name}" — updated ${new Date(data.updated_at).toLocaleString()}.`;

    await refreshHotelTable();
  } catch (err) {
    resultBox.style.display = "block";
    resultBox.className = "result unsafe";
    confirmMsg.textContent = "❌ Failed to save status. Please try again.";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = originalLabel;
  }
});

loadZones();

// ─── Reward redemption code verification ─────────────────────────────────────
const redeemCodeInput = document.getElementById("redeem-code-input");
const redeemFulfilledBy = document.getElementById("redeem-fulfilled-by");
const redeemVerifyBtn = document.getElementById("redeem-verify-btn");
const redeemResultEl = document.getElementById("redeem-verify-result");

redeemVerifyBtn.addEventListener("click", async () => {
  const code = redeemCodeInput.value.trim().toUpperCase();
  if (!code) return;

  const originalLabel = redeemVerifyBtn.textContent;
  redeemVerifyBtn.disabled = true;
  redeemVerifyBtn.textContent = "⏳ Checking…";

  try {
    const res = await fetch(`/api/rewards/redemptions/${encodeURIComponent(code)}/fulfill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fulfilled_by: redeemFulfilledBy.value.trim() || null }),
    });
    const data = await res.json();
    redeemResultEl.innerHTML = `<div class="result ${data.ok ? "safe" : "unsafe"}" style="display:block;">${
      data.ok ? "✅" : "❌"
    } ${data.reason}</div>`;
    if (data.ok) {
      redeemCodeInput.value = "";
    }
  } catch (err) {
    redeemResultEl.innerHTML = `<div class="result unsafe" style="display:block;">❌ Verification failed — please try again.</div>`;
  } finally {
    redeemVerifyBtn.disabled = false;
    redeemVerifyBtn.textContent = originalLabel;
  }
});
