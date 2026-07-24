let totalXp = 0;

const zoneSelect = document.getElementById("zone");
const dateInput = document.getElementById("date");
const form = document.getElementById("tourist-form");
const resultBox = document.getElementById("result");
const badge = document.getElementById("badge");
const dateNoteEl = document.getElementById("date-note");
const explanationEl = document.getElementById("explanation");
const alternativeEl = document.getElementById("alternative");
const xpEl = document.getElementById("xp");

const today = new Date().toISOString().split("T")[0];
dateInput.value = today;
dateInput.min = today;

async function loadZones() {
  const res = await fetch("/api/zones");
  const zones = await res.json();
  zoneSelect.innerHTML = zones
    .map((z) => `<option value="${z.id}">${z.name}</option>`)
    .join("");
}

const submitBtn = form.querySelector(".btn-submit");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const originalLabel = submitBtn.textContent;
  submitBtn.disabled = true;
  submitBtn.textContent = t("analyzing");

  try {
    const res = await fetch("/api/tourist/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        zone_id: zoneSelect.value,
        visit_date: dateInput.value,
        lang: typeof getLang === "function" ? getLang() : "fr",
      }),
    });
    const data = await res.json();

    resultBox.style.display = "block";
    resultBox.className = "result " + (data.safe ? "safe" : "unsafe");
    badge.className = "badge " + (data.safe ? "safe" : "unsafe");
    badge.textContent = data.safe
      ? t("badgeSafe", { score: data.risk_score })
      : t("badgeUnsafe", { score: data.risk_score });
    dateNoteEl.textContent = data.forecast_used
      ? t("dateNoteForecast", { date: data.effective_date })
      : data.effective_date === dateInput.value
        ? t("dateNoteCurrent", { date: data.effective_date })
        : t("dateNoteBeyond", { date: data.effective_date });
    explanationEl.textContent = data.explanation;
    alternativeEl.textContent = data.alternative_zone_name
      ? t("alternativeLabel", { zone: data.alternative_zone_name })
      : "";

    totalXp += data.xp_awarded;
    xpEl.textContent = t("xpTotal", { xp: data.xp_awarded, total: totalXp });
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = originalLabel;
  }
});

loadZones();
