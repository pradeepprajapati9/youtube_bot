"""Growth feedback loop - the data brain.

Records every uploaded video, then periodically pulls its PUBLIC stats
(views / likes / comments via the YouTube Data API - no extra OAuth scope)
and computes an engagement-weighted score. thinker_bot reads the top performers
to make MORE of what actually reaches people, and less of what flops.
"""
import json
import config


def _load():
    if config.PERF_FILE.exists():
        try:
            return json.loads(config.PERF_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {"videos": []}


def _save(data):
    config.PERF_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def record_upload(video_id: str, idea: dict | None, title: str):
    """Log a freshly uploaded video so we can track its performance later."""
    if not video_id:
        return
    data = _load()
    data["videos"].append({
        "video_id": video_id,
        "idea_id": (idea or {}).get("id"),
        "title": title,
        "keywords": (idea or {}).get("keywords", ""),
        "psychology": (idea or {}).get("psychology", ""),
        "views": 0, "likes": 0, "comments": 0, "score": 0,
    })
    data["videos"] = data["videos"][-200:]   # keep it bounded
    _save(data)


def refresh_stats():
    """Pull latest public stats for tracked videos and rescore them."""
    data = _load()
    entries = data["videos"]
    ids = [e["video_id"] for e in entries if e.get("video_id")]
    if not ids:
        return
    if not config.YT_API_KEY:
        print("[analytics] no YT_API_KEY -> feedback loop dormant (add the key to enable)")
        return
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", developerKey=config.YT_API_KEY)
        stats = {}
        for i in range(0, len(ids), 50):            # API allows 50 ids/call
            resp = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
            for it in resp.get("items", []):
                stats[it["id"]] = it.get("statistics", {})
        for e in entries:
            s = stats.get(e["video_id"])
            if s:
                v = int(s.get("viewCount", 0) or 0)
                l = int(s.get("likeCount", 0) or 0)
                c = int(s.get("commentCount", 0) or 0)
                e.update(views=v, likes=l, comments=c, score=v + 20 * l + 50 * c)
        _save(data)
        print(f"[analytics] refreshed stats for {len(stats)} videos")
    except Exception as ex:
        print(f"[analytics] refresh skipped: {ex}")


def top_performers(k: int = 5):
    """Return the k best-performing videos (by engagement-weighted score)."""
    data = _load()
    scored = [e for e in data["videos"] if e.get("score", 0) > 0]
    scored.sort(key=lambda e: e.get("score", 0), reverse=True)
    return scored[:k]


def learnings_summary():
    """A short text summary of what's working, for the thinker's prompt."""
    top = top_performers(5)
    if not top:
        return ""
    parts = [f'"{e["title"]}" ({e["views"]} views, trigger: {e.get("psychology","?")})'
             for e in top]
    return "Past WINNERS on this channel (make MORE like these): " + "; ".join(parts)
