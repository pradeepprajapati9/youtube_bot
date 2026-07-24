"""Auto-daily enqueue (GitHub Actions, once a day).

For every user who has:
  - auto_daily = true and a chosen niche (settings), AND
  - a stored upload token (channel_tokens),
create ONE queued job — unless they already have a pending one. The video
worker then builds + uploads it to that user's channel.
"""
import os
import time
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
_H = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


def _db(method, path, *, headers=None, retries=3, **kw):
    """Supabase REST call with retries (transient timeouts must not kill the run)."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    last = None
    for attempt in range(retries):
        try:
            r = requests.request(method, url, headers=headers or _H, timeout=60, **kw)
            r.raise_for_status()
            return r
        except Exception as ex:
            last = ex
            print(f"[db] {method} {path} attempt {attempt + 1}/{retries} failed: {ex}")
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
    raise last


def sb_get(path, **params):
    return _db("GET", path, params=params).json()


def sb_post(path, row):
    h = dict(_H, **{"Content-Type": "application/json", "Prefer": "return=minimal"})
    _db("POST", path, headers=h, json=row)


def main():
    users = sb_get("settings", auto_daily="eq.true",
                   select="user_id,category,subcategory,language,format")
    print(f"[enqueue] {len(users)} user(s) with auto_daily=true")
    made = 0
    for s in users:
        uid = s["user_id"]
        short = uid[:8]
        if not s.get("category"):
            print(f"[enqueue] skip {short}: no content field set")
            continue
        # must be able to upload (has a refresh token)
        if not sb_get("channel_tokens", user_id=f"eq.{uid}", select="user_id"):
            print(f"[enqueue] skip {short}: no upload token (auto-upload not enabled)")
            continue
        # don't pile up: skip only if a job is already WAITING (queued) for this user.
        # (a stuck 'building' job won't block new slots)
        if sb_get("jobs", user_id=f"eq.{uid}", status="eq.queued", select="id"):
            print(f"[enqueue] skip {short}: a job is already queued")
            continue
        print(f"[enqueue] queued for {short}: {s['category']} > {s.get('subcategory')}")
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
