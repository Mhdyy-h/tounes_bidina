import logging

import httpx

from backend.models import ZoneRisk

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT_SECONDS = 8.0

SYSTEM_PROMPTS = {
    "fr": (
        "Tu es un assistant de sécurité touristique en Tunisie. Tu expliques en français, "
        "simplement et concrètement, pourquoi une zone a un certain niveau de risque "
        "d'incendie, en te basant uniquement sur les chiffres fournis. Ne donne jamais de "
        "conseil médical ou légal. Réponds en 2 à 3 phrases maximum, sans listes ni titres."
    ),
    "en": (
        "You are a tourist safety assistant in Tunisia. You explain in English, simply and "
        "concretely, why a zone has a given wildfire risk level, based only on the figures "
        "provided. Never give medical or legal advice. Answer in 2-3 sentences maximum, "
        "no lists or headings."
    ),
}


def _pick_lowest_risk(candidate_zones: list[ZoneRisk]) -> ZoneRisk | None:
    if not candidate_zones:
        return None
    return min(candidate_zones, key=lambda z: z.risk_score)


def _build_user_prompt(
    zone: dict, risk: ZoneRisk, candidate_zones: list[ZoneRisk], date_context: str, lang: str
) -> str:
    factors = risk.factors

    if lang == "en":
        candidates_txt = ", ".join(
            f"{c.zone_name} (score {c.risk_score})" for c in candidate_zones
        ) or "none"
        return (
            f"Zone: {zone['name']}\n"
            f"Period: {date_context}\n"
            f"Risk score: {risk.risk_score}/100 ({risk.risk_level})\n"
            f"Factors:\n"
            f"- Temperature: {factors.temperature_c:.1f} C\n"
            f"- Wind: {factors.wind_kmh:.1f} km/h\n"
            f"- Humidity: {factors.humidity_pct:.0f} %\n"
            f"- Recent rain: {factors.rain_mm:.1f} mm\n"
            f"- Active fires nearby (15 km): {factors.active_fires_nearby}\n"
            f"- Vegetation index (NDVI): {factors.ndvi:.2f}\n"
            f"Candidate neighboring zones if risk is high: {candidates_txt}\n\n"
            "Explain in 2-3 sentences, in English, why this score is what it is for this "
            "specific period, citing the exact figures above."
        )

    candidates_txt = ", ".join(
        f"{c.zone_name} (score {c.risk_score})" for c in candidate_zones
    ) or "aucune"
    return (
        f"Zone : {zone['name']}\n"
        f"Période : {date_context}\n"
        f"Score de risque : {risk.risk_score}/100 ({risk.risk_level})\n"
        f"Facteurs :\n"
        f"- Température : {factors.temperature_c:.1f} °C\n"
        f"- Vent : {factors.wind_kmh:.1f} km/h\n"
        f"- Humidité : {factors.humidity_pct:.0f} %\n"
        f"- Pluie récente : {factors.rain_mm:.1f} mm\n"
        f"- Foyers actifs à proximité (15 km) : {factors.active_fires_nearby}\n"
        f"- Indice de végétation (NDVI) : {factors.ndvi:.2f}\n"
        f"Zones voisines candidates en cas de risque élevé : {candidates_txt}\n\n"
        "Explique en 2-3 phrases, en français, pourquoi ce score est ce qu'il est pour "
        "cette période précise, en citant les chiffres exacts ci-dessus."
    )


def _fallback_explanation(zone: dict, risk: ZoneRisk, date_context: str, lang: str) -> str:
    factors = risk.factors

    if lang == "en":
        return (
            f"In {zone['name']} ({date_context}), the risk is rated {risk.risk_score}/100 "
            f"({risk.risk_level}): temperature {factors.temperature_c:.1f}C, wind "
            f"{factors.wind_kmh:.1f} km/h, humidity {factors.humidity_pct:.0f}%, "
            f"{factors.rain_mm:.1f}mm recent rain, {factors.active_fires_nearby} active fire(s) "
            f"detected nearby, and a vegetation index (NDVI) of {factors.ndvi:.2f} indicating "
            f"{'dry' if factors.ndvi < 0.4 else 'normal'} vegetation."
        )

    return (
        f"À {zone['name']} ({date_context}), le risque est évalué à {risk.risk_score}/100 "
        f"({risk.risk_level}) : température de {factors.temperature_c:.1f}°C, vent à "
        f"{factors.wind_kmh:.1f} km/h, humidité de {factors.humidity_pct:.0f}%, "
        f"{factors.rain_mm:.1f}mm de pluie récente, {factors.active_fires_nearby} foyer(s) actif(s) "
        f"détecté(s) à proximité, et un indice de végétation (NDVI) de {factors.ndvi:.2f} "
        f"indiquant une végétation {'sèche' if factors.ndvi < 0.4 else 'normale'}."
    )


async def explain_and_recommend(
    zone: dict,
    risk: ZoneRisk,
    candidate_zones: list[ZoneRisk],
    date_context: str = "conditions actuelles",
    lang: str = "fr",
) -> tuple[str, str | None]:
    """
    Returns (explanation, alternative_zone_id).
    Alternative selection is always computed in Python (deterministic, LLM-independent).
    The LLM is only asked to produce the prose explanation.
    `date_context` is a short phrase (already in the target language) describing
    what the numbers reflect (e.g. "conditions actuelles", "forecast for 2026-07-26
    (in 2 days)") - it keeps the explanation honest about whether this is live or
    forecasted. `lang` is "fr" or "en"; anything else falls back to "fr"."""
    lang = lang if lang in SYSTEM_PROMPTS else "fr"
    alternative = _pick_lowest_risk(candidate_zones) if risk.risk_score >= 50 else None
    alternative_zone_id = alternative.zone_id if alternative else None

    prompt = _build_user_prompt(zone, risk, candidate_zones, date_context, lang)

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "system": SYSTEM_PROMPTS[lang],
                    "prompt": prompt,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            explanation = data["response"].strip()
            if not explanation:
                raise ValueError("empty response from Ollama")
            return explanation, alternative_zone_id
    except Exception as exc:
        logger.warning("Ollama call failed (%s), using fallback explanation template", exc)
        return _fallback_explanation(zone, risk, date_context, lang), alternative_zone_id
