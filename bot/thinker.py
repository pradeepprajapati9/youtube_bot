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
import time
import requests
import config

# Try these models in order; on 503/429 (overload/quota) fall through to the next.
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]


def gemini_call(prompt: str, timeout: int = 60) -> str:
    """Resilient Gemini text call with model fallback + one retry. Returns text or ''."""
    if not config.GEMINI_API_KEY:
        return ""
    for attempt in range(2):
        for model in GEMINI_MODELS:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent?key={config.GEMINI_API_KEY}")
            try:
                r = requests.post(url, timeout=timeout,
                                  json={"contents": [{"parts": [{"text": prompt}]}]})
                if r.status_code == 200:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                if r.status_code in (429, 503):
                    continue  # overloaded/quota -> try next model
                print(f"[gemini] {model} http {r.status_code}: {r.text[:140]}")
            except Exception as ex:
                print(f"[gemini] {model} error: {ex}")
        if attempt == 0:
            time.sleep(3)  # brief backoff before the second pass
    return ""


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
    # keep ALL unused ideas, but only the last 80 used ones (enough for de-dup
    # memory) so backlog.json never grows without bound.
    ideas = data.get("ideas", [])
    unused = [i for i in ideas if not i.get("used")]
    used = [i for i in ideas if i.get("used")][-80:]
    data["ideas"] = used + unused
    config.BACKLOG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def _gemini_ideas(existing_titles: list[str], n: int, learnings: str = "", trends: str = ""):
    """Ask Gemini for n fresh, scored video ideas in the niche."""
    if not config.GEMINI_API_KEY:
        return []
    avoid = "; ".join(existing_titles[-40:]) or "none yet"
    prompt = (
        f"You are a top YouTube GROWTH STRATEGIST for a brand-new faceless Shorts channel. "
        f"Your only goal: pick the kinds of videos that will grow the channel's REACH "
        f"(views, subscribers, watch time) the FASTEST, using the psychology of virality "
        f"and human interest (curiosity gaps, emotion, surprise, relatability, share-ability). "
        f"The topic can be ANYTHING in this safe space: {config.NICHE_DESC}\n"
        + (f"\nDATA FROM THIS CHANNEL - {learnings} Lean HARD toward what already works.\n"
           if learnings else "")
        + (f"\n{trends} If any fits the safe space and can be made original and on-brand, "
           f"include ONE timely tie-in idea (trend-riding gets fast reach).\n" if trends else "")
        + "\nUse these PROVEN viral formats where they fit (fill the niche into the blank): "
        "'5 facts you didn't know about ___', '10 things nobody tells you about ___', "
        "'The truth about ___', 'Debunking a common myth about ___', '___ mistakes everyone "
        "makes', 'Why ___ is not what you think', 'Stop believing this about ___', '5 "
        "lesser-known facts about ___', 'What they never told you about ___', 'Why ___ is "
        "more dangerous/amazing than you think'. Keep them faceless-friendly (about the "
        "topic, NOT about a person's life).\n"
        + f"\nBrainstorm {n} NEW, original Short ideas with the highest growth potential. "
        f"Think like a human creator - each needs a real scroll-stopping hook and a fresh "
        f"angle, NOT a generic listicle. Mix topics; choose whatever will get the most reach.\n"
        f"Do NOT repeat or closely resemble these existing ideas: {avoid}.\n"
        f"Return ONLY a valid JSON array. Each item exactly:\n"
        f'{{"title": "...", "hook": "...", "angle": "...", "psychology": "...", '
        f'"keywords": "...", "score": 0}}\n'
        f"Where: title = accurate, curiosity-driving, <85 chars (no clickbait lies); "
        f"hook = the spoken first line; angle = the original take that makes it fresh; "
        f"psychology = the virality trigger it uses (curiosity gap, emotion, relatability, "
        f"surprise, social proof...); keywords = 2-3 words for stock imagery; "
        f"score = your honest 0-100 estimate of REACH/growth + originality potential."
    )
    raw = gemini_call(prompt)
    if not raw:
        return []
    try:
        raw = raw[raw.find("["): raw.rfind("]") + 1]
        ideas = json.loads(raw)
        return ideas if isinstance(ideas, list) else []
    except Exception as ex:
        print(f"[thinker] idea JSON parse failed: {ex}")
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

    # Feed the growth brain: what already works here + today's safe trends.
    learnings, trends = "", ""
    try:
        from bot import analytics
        learnings = analytics.learnings_summary()
    except Exception:
        pass
    try:
        from bot import trending
        safe = [t["title"] for t in trending._fetch_trends(config.TREND_GEO)
                if trending._is_safe(t["title"])][:8]
        if safe:
            trends = "Today's safe trending topics: " + ", ".join(safe) + "."
    except Exception:
        pass

    titles = [i["title"] for i in ideas]
    fresh = _gemini_ideas(titles, config.IDEAS_PER_REFILL, learnings, trends)
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
