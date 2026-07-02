"""Auto-daily enqueue (GitHub Actions, once a day).

For every user who has:
  - auto_daily = true and a chosen niche (settings), AND
  - a stored upload token (channel_tokens),
create ONE queued job — unless they already have a pending one. The video
worker then builds + uploads it to that user's channel.
"""
import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
_H = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


def sb_get(path, **params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=_H, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_post(path, row):
    h = dict(_H, **{"Content-Type": "application/json", "Prefer": "return=minimal"})
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{path}", headers=h, json=row, timeout=30)
    r.raise_for_status()


def main():
    users = sb_get("settings", auto_daily="eq.true",
                   select="user_id,category,subcategory,language,format")
    made = 0
    for s in users:
        uid = s["user_id"]
        if not s.get("category"):
            continue
        # must be able to upload (has a refresh token)
        if not sb_get("channel_tokens", user_id=f"eq.{uid}", select="user_id"):
            continue
        # don't pile up: skip only if a job is already WAITING (queued) for this user.
        # (a stuck 'building' job won't block new slots)
        if sb_get("jobs", user_id=f"eq.{uid}", status="eq.queued", select="id"):
            continue
        sb_post("jobs", {
            "user_id": uid,
            "category": s["category"],
            "subcategory": s.get("subcategory"),
            "language": s.get("language") or "en",
            "format": s.get("format") or "short",
            "status": "queued",
        })
        made += 1
    print(f"[enqueue] created {made} daily job(s)")


if __name__ == "__main__":
    main()
