const TRANSLATIONS = {
  fr: {
    navDashboard: "Tableau de bord",
    navTourist: "Espace touriste (simple)",
    navPortal: "Portail touriste",
    navHotel: "Portail hôtelier",
    navMap: "Carte",
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
    chatButtonLabel: "Ouvrir le guide touristique",
    chatTitle: "Guide touristique IA",
    chatWelcome: "Bonjour ! Je suis votre guide touristique IA pour la Tunisie. Posez-moi une question sur une zone, un hôtel ou une activité.",
    chatPlaceholder: "Écrivez votre question…",
    chatSend: "Envoyer",
    chatThinking: "Réflexion en cours…",
    chatError: "Erreur de connexion — veuillez réessayer.",
  },
  en: {
    navDashboard: "Dashboard",
    navTourist: "Tourist area (simple)",
    navPortal: "Tourist Portal",
    navHotel: "Hotel Portal",
    navMap: "Map",
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
    chatButtonLabel: "Open tourist guide",
    chatTitle: "AI Tourist Guide",
    chatWelcome: "Hi! I'm your AI tourist guide for Tunisia. Ask me about a zone, hotel, or activity.",
    chatPlaceholder: "Type your question…",
    chatSend: "Send",
    chatThinking: "Thinking…",
    chatError: "Connection error — please try again.",
  },
  ar: {
    navDashboard: "لوحة التحكم",
    navTourist: "الفضاء السياحي (مبسط)",
    navPortal: "البوابة السياحية",
    navHotel: "بوابة الفنادق",
    navMap: "الخريطة",
    triggerScenario: "🔥 تفعيل سيناريو حريق (عين دراهم)",
    resetScenario: "↺ إعادة تعيين",
    refreshNdvi: "🛰️ تحديث مؤشر NDVI الفضائي",
    legendLow: "منخفض",
    legendMedium: "متوسط",
    legendHigh: "مرتفع",
    legendCritical: "حرج",
    touristTitle: "هل يمكنني زيارة هذه المنطقة؟",
    zoneLabel: "المنطقة",
    dateLabel: "تاريخ الزيارة",
    dateHint: "توقعات جوية حقيقية حتى 3 أيام مقدمًا؛ بعد ذلك تُستخدم الظروف الحالية.",
    submitBtn: "تحقق",
    analyzing: "⏳ جارٍ التحليل (ذكاء اصطناعي)…",
    badgeSafe: "آمن (النتيجة {score}/100)",
    badgeUnsafe: "خطر مرتفع (النتيجة {score}/100)",
    dateNoteForecast: "📅 استنادًا إلى توقعات جوية حقيقية ليوم {date}",
    dateNoteCurrent: "📅 استنادًا إلى الظروف الحالية ({date})",
    dateNoteBeyond: "📅 التاريخ يتجاوز مدة التوقع الموثوق — استُخدمت بدلاً منه الظروف الحالية ليوم {date}",
    alternativeLabel: "البديل الموصى به: {zone}",
    xpTotal: "+{xp} نقطة خبرة — المجموع: {total} نقطة",
    dashboardTagline: "لوحة التحكم — وزارة السياحة والحماية المدنية",
    statTotal: "المناطق المراقَبة",
    statCritical: "حرج",
    statHigh: "مرتفع",
    statAvg: "متوسط النتيجة",
    statNdvi: "مؤشر NDVI فضائي حقيقي",
    tableZone: "المنطقة",
    tableRisk: "الخطر",
    tableLevel: "المستوى",
    tableConfidence: "ثقة السائح*",
    tableTemp: "الحرارة",
    tableWind: "الرياح",
    tableHumidity: "الرطوبة",
    tableFires: "الحرائق النشطة",
    tableUpdated: "آخر تحديث",
    dashboardFootnote: "* ثقة السائح = 100 − نتيجة الخطر. عرض مبسط لهذا العرض التوضيحي، وليس نموذجًا منفصلاً — المقياس الكامل (الوصول، سعة الفنادق، التنبيهات النشطة...) جزء من الرؤية طويلة المدى للمشروع.",
    chatButtonLabel: "فتح المرشد السياحي",
    chatTitle: "المرشد السياحي الذكي",
    chatWelcome: "مرحبًا! أنا مرشدك السياحي الذكي في تونس. اسألني عن أي منطقة أو فندق أو نشاط.",
    chatPlaceholder: "اكتب سؤالك هنا…",
    chatSend: "إرسال",
    chatThinking: "جارٍ التفكير…",
    chatError: "خطأ في الاتصال — يرجى المحاولة مرة أخرى.",
  },
};

const LANGS = ["fr", "en", "ar"];
const RTL_LANGS = ["ar"];

function getLang() {
  const stored = localStorage.getItem("tg_lang");
  return LANGS.includes(stored) ? stored : "fr";
}

function isRtl(lang) {
  return RTL_LANGS.includes(lang || getLang());
}

function nextLang(lang) {
  const idx = LANGS.indexOf(lang);
  return LANGS[(idx + 1) % LANGS.length];
}

function setLang(lang) {
  localStorage.setItem("tg_lang", lang);
  applyTranslations();
  document.dispatchEvent(new CustomEvent("langchange", { detail: { lang } }));
}

function cycleLang() {
  setLang(nextLang(getLang()));
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
  const lang = getLang();
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.documentElement.lang = lang;
  document.documentElement.dir = isRtl(lang) ? "rtl" : "ltr";
  const btn = document.getElementById("lang-toggle");
  if (btn) {
    btn.textContent = nextLang(lang).toUpperCase();
    btn.title = `${lang.toUpperCase()} → ${nextLang(lang).toUpperCase()}`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  applyTranslations();
  const btn = document.getElementById("lang-toggle");
  if (btn) {
    btn.addEventListener("click", cycleLang);
  }
});
