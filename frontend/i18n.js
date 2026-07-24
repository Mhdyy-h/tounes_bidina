const TRANSLATIONS = {
  fr: {
    navDashboard: "Tableau de bord",
    navTourist: "Espace touriste →",
    navMap: "← Carte",
    triggerScenario: "🔥 Déclencher scénario incendie (Aïn Draham)",
    resetScenario: "↺ Réinitialiser",
    refreshNdvi: "🛰️ Actualiser NDVI satellite",
    legendLow: "Faible",
    legendMedium: "Moyen",
    legendHigh: "Élevé",
    legendCritical: "Critique",
    touristTitle: "Puis-je visiter cette zone ?",
    zoneLabel: "Zone",
    dateLabel: "Date de visite",
    dateHint: "Prévision météo réelle jusqu'à J+3 ; au-delà, conditions actuelles utilisées.",
    submitBtn: "Vérifier",
    analyzing: "⏳ Analyse en cours (IA)…",
    badgeSafe: "Sûr (score {score}/100)",
    badgeUnsafe: "Risque élevé (score {score}/100)",
    dateNoteForecast: "📅 Basé sur une prévision météo réelle pour le {date}",
    dateNoteCurrent: "📅 Basé sur les conditions actuelles ({date})",
    dateNoteBeyond: "📅 Date au-delà de la prévision fiable — conditions actuelles du {date} utilisées à la place",
    alternativeLabel: "Alternative recommandée : {zone}",
    xpTotal: "+{xp} XP — Total : {total} XP",
    dashboardTagline: "Tableau de bord — Ministère du Tourisme & Protection Civile",
    statTotal: "Zones surveillées",
    statCritical: "Critique",
    statHigh: "Élevé",
    statAvg: "Score moyen",
    statNdvi: "NDVI satellite réel",
    tableZone: "Zone",
    tableRisk: "Risque",
    tableLevel: "Niveau",
    tableConfidence: "Confiance touristique*",
    tableTemp: "Temp.",
    tableWind: "Vent",
    tableHumidity: "Humidité",
    tableFires: "Foyers actifs",
    tableUpdated: "Dernière MAJ",
    dashboardFootnote: "* Confiance touristique = 100 − score de risque. Aperçu simplifié pour cette démo, pas un modèle distinct — la métrique complète (accès, capacité hôtelière, alertes actives...) fait partie de la vision long terme du projet.",
  },
  en: {
    navDashboard: "Dashboard",
    navTourist: "Tourist area →",
    navMap: "← Map",
    triggerScenario: "🔥 Trigger fire scenario (Aïn Draham)",
    resetScenario: "↺ Reset",
    refreshNdvi: "🛰️ Refresh satellite NDVI",
    legendLow: "Low",
    legendMedium: "Medium",
    legendHigh: "High",
    legendCritical: "Critical",
    touristTitle: "Can I visit this area?",
    zoneLabel: "Zone",
    dateLabel: "Visit date",
    dateHint: "Real weather forecast up to D+3; beyond that, current conditions are used.",
    submitBtn: "Check",
    analyzing: "⏳ Analyzing (AI)…",
    badgeSafe: "Safe (score {score}/100)",
    badgeUnsafe: "High risk (score {score}/100)",
    dateNoteForecast: "📅 Based on a real weather forecast for {date}",
    dateNoteCurrent: "📅 Based on current conditions ({date})",
    dateNoteBeyond: "📅 Date beyond the reliable forecast — current conditions from {date} used instead",
    alternativeLabel: "Recommended alternative: {zone}",
    xpTotal: "+{xp} XP — Total: {total} XP",
    dashboardTagline: "Dashboard — Ministry of Tourism & Civil Protection",
    statTotal: "Zones monitored",
    statCritical: "Critical",
    statHigh: "High",
    statAvg: "Average score",
    statNdvi: "Real satellite NDVI",
    tableZone: "Zone",
    tableRisk: "Risk",
    tableLevel: "Level",
    tableConfidence: "Tourist confidence*",
    tableTemp: "Temp.",
    tableWind: "Wind",
    tableHumidity: "Humidity",
    tableFires: "Active fires",
    tableUpdated: "Last update",
    dashboardFootnote: "* Tourist confidence = 100 - risk score. Simplified preview for this demo, not a separate model - the full metric (access, hotel capacity, active alerts...) is part of the project's long-term vision.",
  },
};

function getLang() {
  return localStorage.getItem("tg_lang") || "fr";
}

function setLang(lang) {
  localStorage.setItem("tg_lang", lang);
  applyTranslations();
  document.dispatchEvent(new CustomEvent("langchange", { detail: { lang } }));
}

function t(key, params) {
  let str = (TRANSLATIONS[getLang()] && TRANSLATIONS[getLang()][key]) || TRANSLATIONS.fr[key] || key;
  if (params) {
    Object.keys(params).forEach((k) => {
      str = str.replace(`{${k}}`, params[k]);
    });
  }
  return str;
}

function applyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.documentElement.lang = getLang();
  const btn = document.getElementById("lang-toggle");
  if (btn) btn.textContent = getLang() === "fr" ? "EN" : "FR";
}

document.addEventListener("DOMContentLoaded", () => {
  applyTranslations();
  const btn = document.getElementById("lang-toggle");
  if (btn) {
    btn.addEventListener("click", () => setLang(getLang() === "fr" ? "en" : "fr"));
  }
});
