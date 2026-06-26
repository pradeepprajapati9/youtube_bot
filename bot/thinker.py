"""thinker_bot - the channel's growth brain.

It continuously thinks AHEAD: brainstorms video ideas inside the channel's niche,
scores each for viral + original potential (the score doubles as a spam guard),
and keeps a ranked backlog in backlog.json so a video is always ready to make -
no time wasted "searching" at upload time.

Only ideas scoring >= QUALITY_THRESHOLD are ever produced, which keeps the channel
on the right side of YouTube's "inauthentic / mass-produced content" policy.
"""
import re
import json
import requests
import config


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def _load():
    if config.BACKLOG_FILE.exists():
        try:
            return json.loads(config.BACKLOG_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {"ideas": []}


def _save(data):
    config.BACKLOG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def _gemini_ideas(existing_titles: list[str], n: int):
    """Ask Gemini for n fresh, scored video ideas in the niche."""
    if not config.GEMINI_API_KEY:
        return []
    avoid = "; ".join(existing_titles[-40:]) or "none yet"
    prompt = (
        f"You are a viral YouTube Shorts strategist for a faceless channel in the niche: "
        f"'{config.NICHE}' ({config.NICHE_DESC}).\n"
        f"Brainstorm {n} NEW, original Short ideas that would genuinely grow the channel "
        f"toward monetization (subscribers + watch time). Think like a human creator: each "
        f"idea needs a real hook and a fresh angle, NOT a generic listicle.\n"
        f"Do NOT repeat or closely resemble these existing ideas: {avoid}.\n"
        f"Return ONLY a valid JSON array. Each item exactly:\n"
        f'{{"title": "...", "hook": "...", "angle": "...", "psychology": "...", '
        f'"keywords": "...", "score": 0}}\n'
        f"Where: title = accurate, curiosity-driving, <85 chars (no clickbait lies); "
        f"hook = the spoken first line; angle = the original take that makes it fresh; "
        f"psychology = the human trigger it uses (curiosity gap, emotion, relatability, "
        f"surprise, social proof...); keywords = 2-3 words for stock imagery; "
        f"score = your honest 0-100 estimate of viral + originality potential."
    )
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               "gemini-2.5-flash:generateContent?key=" + config.GEMINI_API_KEY)
        r = requests.post(url, timeout=60, json={"contents": [{"parts": [{"text": prompt}]}]})
        if r.status_code != 200:
            print(f"[thinker] gemini http {r.status_code}: {r.text[:160]}")
            return []
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        raw = raw[raw.find("["): raw.rfind("]") + 1]
        ideas = json.loads(raw)
        return ideas if isinstance(ideas, list) else []
    except Exception as ex:
        print(f"[thinker] gemini failed: {ex}")
        return []


def top_up():
    """Refill the backlog if it's running low on quality unused ideas."""
    data = _load()
    ideas = data["ideas"]
    known = {i["id"] for i in ideas}
    unused_good = [i for i in ideas if not i.get("used")
                   and i.get("score", 0) >= config.QUALITY_THRESHOLD]

    if len(unused_good) >= config.BACKLOG_MIN:
        return  # plenty queued

    titles = [i["title"] for i in ideas]
    fresh = _gemini_ideas(titles, config.IDEAS_PER_REFILL)
    added = 0
    for it in fresh:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        iid = _slug(title)
        if iid in known:
            continue
        known.add(iid)
        ideas.append({
            "id": iid,
            "title": title,
            "hook": it.get("hook", ""),
            "angle": it.get("angle", ""),
            "psychology": it.get("psychology", ""),
            "keywords": it.get("keywords", config.NICHE),
            "score": int(it.get("score", 0) or 0),
            "used": False,
        })
        added += 1
    if added:
        _save(data)
    print(f"[thinker] added {added} ideas "
          f"(backlog now {sum(1 for i in ideas if not i.get('used'))} unused)")


def next_idea():
    """Return the highest-scoring unused idea above the quality bar, or None."""
    data = _load()
    candidates = [i for i in data["ideas"] if not i.get("used")
                  and i.get("score", 0) >= config.QUALITY_THRESHOLD]
    if not candidates:
        return None
    candidates.sort(key=lambda i: i.get("score", 0), reverse=True)
    best = candidates[0]
    print(f"[thinker] picked idea (score {best['score']}): {best['title']}")
    return best


def mark_used(idea_id: str):
    data = _load()
    for i in data["ideas"]:
        if i["id"] == idea_id:
            i["used"] = True
    _save(data)


if __name__ == "__main__":
    top_up()
    print(next_idea())
