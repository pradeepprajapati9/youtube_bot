"""Pick a 'demanding' (trending) topic automatically - FREE, no API key.

Source: Google Trends 'trending now' RSS feed. Returns the top trending
search term we haven't used yet, plus a rich context built from ALL the
related news snippets (better raw material for the script).
"""
import json
import xml.etree.ElementTree as ET
import requests
import config


def _load_used():
    if config.STATE_FILE.exists():
        try:
            return set(json.loads(config.STATE_FILE.read_text("utf-8")).get("used_topics", []))
        except Exception:
            return set()
    return set()


def mark_used(topic: str):
    used = _load_used()
    used.add(topic.lower())
    config.STATE_FILE.write_text(
        json.dumps({"used_topics": sorted(used)}, ensure_ascii=False, indent=2), "utf-8"
    )


def _local(tag: str) -> str:
    return tag.split("}")[-1]  # strip XML namespace


# Trending feeds are full of crime/tragedy/politics that are unsafe for an
# auto-uploaded faceless channel (age-restriction / demonetization / strikes).
# Any topic containing these words is skipped.
BLOCKLIST = {
    "stabbing", "stabbed", "murder", "killed", "kill", "death", "dead", "die",
    "rape", "assault", "attack", "shooting", "shot", "bomb", "blast", "terror",
    "suicide", "accident", "crash", "fire", "riot", "war", "abuse", "arrest",
    "scam", "fraud", "viral video", "leaked", "mms", "sex", "nude", "drugs",
    "protest", "election", "vote", "bjp", "congress", "modi", "trump", "porn",
}


def _is_safe(title: str) -> bool:
    low = title.lower()
    return not any(bad in low for bad in BLOCKLIST)


def _fetch_trends(geo: str):
    """Return list of {title, context} where context joins all news snippets."""
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    out = []
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        for item in root.iter("item"):
            title, snippets = "", []
            for child in item:
                name = _local(child.tag)
                if name == "title":
                    title = (child.text or "").strip()
                elif name == "news_item":
                    for nc in child:
                        if _local(nc.tag) in ("news_item_title", "news_item_snippet"):
                            if nc.text:
                                snippets.append(nc.text.strip())
            if title:
                out.append({"title": title, "context": " ".join(snippets)})
    except Exception as ex:
        print(f"[trending] RSS parse failed: {ex}")
    return out


def pick_topic():
    """Return (topic, context). Skips already-used topics."""
    used = _load_used()
    for t in _fetch_trends(config.TREND_GEO):
        if t["title"].lower() in used:
            continue
        if not _is_safe(t["title"]):
            print(f"[trending] skipped (unsafe): {t['title']}")
            continue
        print(f"[trending] picked: {t['title']}")
        return t["title"], t["context"]

    # Evergreen, high-retention fallbacks (great for faceless Shorts)
    fallback = [
        "Amazing facts about space",
        "Mysteries of the human brain",
        "Incredible facts about the ocean",
        "Psychological tricks that actually work",
        "Facts that sound fake but are true",
        "Unsolved mysteries of history",
    ]
    for f in fallback:
        if f.lower() not in used:
            print(f"[trending] using fallback topic: {f}")
            return f, ""
    return fallback[0], ""


if __name__ == "__main__":
    print(pick_topic())
