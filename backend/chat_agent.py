import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT_SECONDS = 20.0
MAX_HISTORY_MESSAGES = 20

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SYSTEM_PROMPTS = {
    "fr": (
        "Tu es le guide touristique IA de Tunisia Guardian AI, une plateforme d'aide à la "
        "décision touristique pour 6 zones du nord de la Tunisie. Tu réponds aux questions des "
        "touristes sur la sécurité, les sites, les activités et l'hébergement, en te basant "
        "UNIQUEMENT sur les données fournies ci-dessous (scores de risque en direct, hôtels "
        "déclarés, descriptions des sites). Si une information ne figure pas dans ces données "
        "(horaires précis, prix, disponibilité exacte), dis clairement que tu ne l'as pas plutôt "
        "que de l'inventer. Ne donne jamais de conseil médical ou légal. Réponds de façon "
        "concise et chaleureuse, en 2 à 5 phrases sauf si on te demande plus de détails."
    ),
    "en": (
        "You are the AI tourist guide for Tunisia Guardian AI, a tourism decision-support "
        "platform covering 6 zones in northern Tunisia. You answer tourist questions about "
        "safety, sites, activities, and lodging, based ONLY on the data provided below (live "
        "risk scores, declared hotels, site descriptions). If a piece of information isn't in "
        "this data (exact hours, prices, exact availability), clearly say you don't have it "
        "rather than inventing it. Never give medical or legal advice. Answer concisely and "
        "warmly, in 2-5 sentences unless asked for more detail."
    ),
    "ar": (
        "أنت المرشد السياحي الذكي لمنصة Tunisia Guardian AI، وهي منصة لمساعدة السياح في اتخاذ "
        "القرار وتغطي 6 مناطق في شمال تونس. تجيب على أسئلة السياح حول السلامة والمواقع والأنشطة "
        "والإقامة، بالاعتماد فقط على البيانات المقدمة أدناه (درجات الخطر الحية، الفنادق المسجّلة، "
        "أوصاف المواقع). إذا لم تكن المعلومة متوفرة في هذه البيانات (كالمواعيد الدقيقة أو الأسعار "
        "أو التوفر الدقيق)، صرّح بوضوح أنك لا تملكها بدلاً من اختلاقها. لا تقدّم أبدًا نصيحة طبية "
        "أو قانونية. أجب بإيجاز وبأسلوب ودود، في جملتين إلى خمس جمل إلا إذا طُلب منك مزيد من التفاصيل."
    ),
}

FALLBACK_MESSAGES = {
    "fr": (
        "Le guide IA n'est pas disponible pour le moment (le service local Ollama ne répond "
        "pas). En attendant, consultez le tableau de bord pour les scores de risque par zone, "
        "ou le portail hôtelier pour la disponibilité des chambres."
    ),
    "en": (
        "The AI guide isn't available right now (the local Ollama service isn't responding). "
        "In the meantime, check the dashboard for per-zone risk scores, or the hotel portal "
        "for room availability."
    ),
    "ar": (
        "المرشد الذكي غير متوفر حاليًا (خدمة Ollama المحلية لا تستجيب). في هذه الأثناء، يمكنك "
        "مراجعة لوحة التحكم لمعرفة درجات الخطر لكل منطقة، أو بوابة الفنادق لمعرفة الغرف المتاحة."
    ),
}

RISK_LEVEL_LABELS = {
    "fr": {"low": "faible", "medium": "moyen", "high": "élevé", "critical": "critique"},
    "en": {"low": "low", "medium": "medium", "high": "high", "critical": "critical"},
    "ar": {"low": "منخفض", "medium": "متوسط", "high": "مرتفع", "critical": "حرج"},
}

_zone_guide_cache: dict | None = None


def _load_zone_guide() -> dict:
    global _zone_guide_cache
    if _zone_guide_cache is None:
        with open(DATA_DIR / "zone_guide.json", encoding="utf-8") as f:
            _zone_guide_cache = json.load(f)
    return _zone_guide_cache


def _build_context_block(
    zones_context: list[dict], hotel_summary: dict | None, lang: str
) -> str:
    guide = _load_zone_guide()
    level_labels = RISK_LEVEL_LABELS.get(lang, RISK_LEVEL_LABELS["fr"])

    lines = []
    header = {
        "fr": "=== Données en direct (Tunisia Guardian AI) ===",
        "en": "=== Live data (Tunisia Guardian AI) ===",
        "ar": "=== بيانات حية (Tunisia Guardian AI) ===",
    }[lang if lang in ("fr", "en", "ar") else "fr"]
    lines.append(header)

    for z in zones_context:
        entry = guide.get(z["id"], {})
        desc = entry.get("description", {}).get(lang, "")
        highlights = entry.get("highlights", {}).get(lang, [])
        level = level_labels.get(z["fire_risk_level"], z["fire_risk_level"])
        lines.append(
            f"\n- {z['name']} (id={z['id']}): "
            f"{'fire/wildfire risk' if lang == 'en' else 'risque incendie' if lang == 'fr' else 'خطر الحرائق'} "
            f"{z['fire_risk_score']}/100 ({level}). {desc}"
        )
        if highlights:
            lines.append(f"  {'Highlights' if lang == 'en' else 'Points forts' if lang == 'fr' else 'أبرز المعالم'}: "
                          + ", ".join(highlights))

    if hotel_summary:
        if lang == "en":
            lines.append(
                f"\nHotel network: {hotel_summary.get('total_hotels', 0)} declared hotels, "
                f"{hotel_summary.get('operational_pct', 0):.0f}% currently operational, "
                f"{hotel_summary.get('rooms_available_in_safe_zones', 0)} rooms available in "
                f"currently safe zones."
            )
        elif lang == "ar":
            lines.append(
                f"\nشبكة الفنادق: {hotel_summary.get('total_hotels', 0)} فندق مسجّل، "
                f"{hotel_summary.get('operational_pct', 0):.0f}% منها يعمل حاليًا، "
                f"و{hotel_summary.get('rooms_available_in_safe_zones', 0)} غرفة متاحة في المناطق "
                f"الآمنة حاليًا."
            )
        else:
            lines.append(
                f"\nRéseau hôtelier : {hotel_summary.get('total_hotels', 0)} hôtels déclarés, "
                f"{hotel_summary.get('operational_pct', 0):.0f}% opérationnels actuellement, "
                f"{hotel_summary.get('rooms_available_in_safe_zones', 0)} chambres disponibles "
                f"dans les zones actuellement sûres."
            )

    return "\n".join(lines)


async def chat_reply(
    messages: list[dict],
    zones_context: list[dict],
    hotel_summary: dict | None,
    lang: str = "fr",
) -> tuple[str, bool]:
    """
    Returns (reply_text, used_llm). `messages` is the conversation history as
    [{"role": "user"|"assistant", "content": str}, ...] (already capped by the
    caller). Grounding context (live zone risk + hotel stats + static site
    descriptions) is injected as a system message so the model answers from
    real data instead of inventing facts - same honesty discipline as the
    rest of this project: if Ollama is unreachable, we say so plainly instead
    of pretending the AI answered.
    """
    lang = lang if lang in SYSTEM_PROMPTS else "fr"
    context_block = _build_context_block(zones_context, hotel_summary, lang)
    system_message = {"role": "system", "content": f"{SYSTEM_PROMPTS[lang]}\n\n{context_block}"}
    chat_messages = [system_message] + messages[-MAX_HISTORY_MESSAGES:]

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                OLLAMA_CHAT_URL,
                json={"model": OLLAMA_MODEL, "messages": chat_messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["message"]["content"].strip()
            if not reply:
                raise ValueError("empty response from Ollama")
            return reply, True
    except Exception as exc:
        logger.warning("Ollama chat call failed (%s), using fallback message", exc)
        return FALLBACK_MESSAGES[lang], False
