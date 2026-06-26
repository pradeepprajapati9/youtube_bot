"""Turn a topic into a SCENE-BASED script for a faceless Short - FREE.

Returns a dict:
  {
    "title": str, "description": str, "tags": [str],
    "scenes": [ {"narration": str, "keyword": str}, ... ]   # 4-6 scenes
  }

Content sources (in order): Gemini (if key) -> Wikipedia + trend news -> template.
Each scene has a 'keyword' used to fetch a matching image/clip in visuals.py.
"""
import re
import json
import requests
import config

N_SCENES = 5


def _clean(text: str) -> str:
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sentences(text: str):
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def _wikipedia(topic: str) -> str:
    try:
        t = requests.utils.quote(topic.replace(" ", "_"))
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{t}",
            timeout=15, headers={"User-Agent": "yt-bot/1.0"},
        )
        if r.status_code == 200:
            return _clean(r.json().get("extract", ""))
    except Exception as ex:
        print(f"[script] wikipedia failed: {ex}")
    return ""


def _keywords(topic: str, narration: str) -> str:
    """Pick a short visual search phrase for a scene."""
    # prefer capitalized entities from narration, else the topic
    caps = re.findall(r"\b[A-Z][a-z]{3,}\b", narration)
    if caps:
        return " ".join(caps[:2])
    return topic


def _gemini_scenes(topic: str, ctx: str):
    if not config.GEMINI_API_KEY:
        return None
    lang = "Hindi" if config.LANG == "hi" else "English"
    prompt = (
        f"You are scripting a viral 50-second faceless YouTube Short in {lang} about: '{topic}'.\n"
        f"Extra context: {ctx or 'none'}.\n"
        f"Return ONLY valid JSON, no markdown, with this exact shape:\n"
        f'{{"title": "...", "description": "...", "tags": ["..."], '
        f'"scenes": [{{"narration": "...", "keyword": "..."}}]}}\n'
        f"Rules: exactly {N_SCENES} scenes. Scene 1 narration MUST be a strong hook. "
        f"Each narration 18-28 words, spoken plain text (no emojis). "
        f"'keyword' = 2-3 English words describing a stock image for that scene. "
        f"Last scene ends asking viewers to follow. Title under 90 chars with #Shorts.\n"
        f"SAFETY: state only well-established, verifiable facts - no made-up statistics, "
        f"no medical/financial/legal advice, no defamation, no shocking/violent claims. "
        f"Title must be accurate and NOT clickbait or misleading."
    )
    from bot.thinker import gemini_call
    raw = gemini_call(prompt, timeout=45)
    if not raw:
        return None
    try:
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        data = json.loads(raw)
        if data.get("scenes"):
            return data
    except Exception as ex:
        print(f"[script] scene JSON parse failed: {ex}")
    return None


def _fallback_scenes(topic: str, ctx: str):
    """Free, no-LLM: build scenes from Wikipedia + trend news context."""
    body = " ".join(x for x in (_wikipedia(topic), _clean(ctx)) if x).strip()
    sents = _sentences(body)

    if not sents:
        sents = [
            f"Here's something interesting about {topic}.",
            f"{topic} is trending everywhere right now.",
            "And the reason might surprise you.",
        ]

    # group sentences into N_SCENES scenes
    scenes, i = [], 0
    per = max(1, len(sents) // N_SCENES)
    while i < len(sents) and len(scenes) < N_SCENES:
        chunk = " ".join(sents[i:i + per])
        scenes.append(chunk)
        i += per
    # always end with a follow CTA
    cta = "Aage aur jaan-ne ke liye follow karo!" if config.LANG == "hi" \
        else "Follow for more!"
    scenes.append(cta)

    return {
        "title": f"{topic} | #Shorts",
        "description": f"{topic}\n\n{body[:160]}...",
        "tags": ["shorts", "trending", "facts", "viral"],
        "scenes": [{"narration": s, "keyword": _keywords(topic, s)} for s in scenes if s],
    }


def generate(topic: str, context: str = "") -> dict:
    data = _gemini_scenes(topic, context) or _fallback_scenes(topic, context)

    # sanitize / clamp
    scenes = []
    for sc in data["scenes"][:N_SCENES + 1]:
        narr = _clean(sc.get("narration", ""))
        if narr:
            scenes.append({"narration": narr,
                           "keyword": (sc.get("keyword") or _keywords(topic, narr)).strip()})
    data["scenes"] = scenes or [{"narration": f"Facts about {topic}. Follow for more!",
                                 "keyword": topic}]

    title = data.get("title") or f"{topic} | #Shorts"
    if "#short" not in title.lower():
        title = (title[:88] + " #Shorts")
    data["title"] = title[:100]

    base_tags = ["shorts", "trending", "facts", "viral"]
    data["tags"] = (data.get("tags") or []) + base_tags
    data["tags"] = list(dict.fromkeys([t.strip() for t in data["tags"] if t.strip()]))[:12]

    if not data.get("description"):
        data["description"] = topic
    data["description"] += "\n\n#Shorts #trending #facts #viral"
    return data


if __name__ == "__main__":
    print(json.dumps(generate("Black holes", ""), indent=2, ensure_ascii=False))
