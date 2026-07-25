/**
 * Landing page opened when a tourist scans a checkpoint's printed QR code
 * (or taps a "check in now" link from the rewards page). The checkpoint_id
 * comes from the URL path (/checkin/{id}), the signature from ?sig=. Real
 * browser geolocation is required - the backend enforces the geofence, this
 * page just collects and forwards the position.
 */

function parseCheckpointId() {
  const match = window.location.pathname.match(/\/checkin\/([^/?]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error(t("checkinGeoUnsupported")));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => reject(new Error(t("checkinGeoDenied"))),
      { enableHighAccuracy: true, timeout: 15000 }
    );
  });
}

function showResult(ok, message, balance) {
  document.getElementById("checkin-spinner").style.display = "none";
  document.getElementById("checkin-status").style.display = "none";
  document.getElementById("checkin-title").textContent = t(
    ok ? "checkinSuccessTitle" : "checkinFailedTitle"
  );

  const resultEl = document.getElementById("checkin-result");
  const badgeEl = document.getElementById("checkin-badge");
  resultEl.className = `result ${ok ? "safe" : "unsafe"}`;
  resultEl.style.display = "block";
  badgeEl.className = `badge ${ok ? "safe" : "unsafe"}`;
  badgeEl.textContent = ok ? "✓" : "✕";
  document.getElementById("checkin-message").textContent = message;
  document.getElementById("checkin-balance").textContent =
    balance != null ? t("checkinBalance", { balance }) : "";
}

async function runCheckin() {
  const checkpointId = parseCheckpointId();
  const sig = new URLSearchParams(window.location.search).get("sig");

  if (!checkpointId || !sig) {
    showResult(false, t("checkinInvalidLink"), null);
    return;
  }

  try {
    document.getElementById("checkin-status").textContent = t("checkinLocating");
    const pos = await getCurrentPosition();

    document.getElementById("checkin-status").textContent = t("checkinChecking");
    const resp = await fetch(`/api/rewards/checkin/${encodeURIComponent(checkpointId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tourist_id: getTouristId(),
        lat: pos.lat,
        lon: pos.lon,
        sig,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showResult(false, data.detail || t("checkinInvalidLink"), null);
      return;
    }
    showResult(data.ok, data.reason, data.new_balance);
  } catch (err) {
    showResult(false, err.message, null);
  }
}

document.addEventListener("DOMContentLoaded", runCheckin);
