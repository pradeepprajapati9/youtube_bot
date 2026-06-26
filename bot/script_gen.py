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
        f"You are a viral retention expert scripting a 45-second faceless YouTube Short "
        f"in {lang} about: '{topic}'. Extra context: {ctx or 'none'}.\n"
        f"Your ONE job is maximum watch-time + shares using proven psychology.\n"
        f"Return ONLY valid JSON, no markdown, exact shape:\n"
        f'{{"title": "...", "description": "...", "tags": ["..."], '
        f'"scenes": [{{"narration": "...", "keyword": "..."}}]}}\n'
        f"RETENTION FORMULA - follow exactly across {N_SCENES} scenes:\n"
        f"- Scene 1 = a SCROLL-STOPPER hook (max 12 words): a shocking claim or a "
        f"question that opens a curiosity loop the viewer NEEDS resolved. No intro, "
        f"no 'today we'll learn'. Punch instantly.\n"
        f"- Middle scenes = deliver fast, SPECIFIC, surprising value; each one escalates "
        f"curiosity so they can't swipe away. Short, vivid, simple spoken words.\n"
        f"- Final scene = pay off the loop with the most surprising point, then ONE casual "
        f"engagement line that invites a comment (e.g. ask the viewer a question), and end "
        f"with a line that loops back to the hook so a replay feels seamless. Include 'follow "
        f"for more'.\n"
        f"Each narration 12-24 words, conversational, no emojis. "
        f"'keyword' = 2-3 English words for a matching stock clip. "
        f"Title = curiosity-driving but ACCURATE (no clickbait lies), under 85 chars, add #Shorts.\n"
        f"SAFETY: only well-established verifiable facts - no made-up statistics, no "
        f"medical/financial/legal advice, no defamation, no shocking/violent claims."
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
