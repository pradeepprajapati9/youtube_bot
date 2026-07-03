"""Multi-user video worker (GitHub Actions).

Reads `queued` jobs from Supabase, builds a video for each user's chosen niche
using the SAME free pipeline (script -> voiceover -> visuals -> edit), then
uploads it to THAT user's own channel using their stored refresh token.

Env (from GitHub Secrets):
  SUPABASE_URL, SUPABASE_SERVICE_KEY   -> the DB (service key bypasses RLS to read tokens)
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET -> to mint per-user access tokens
  GEMINI_API_KEY (optional), PEXELS_API_KEY (optional)
  YT_PRIVACY (default 'private'), MAX_JOBS (default 3)
"""
import os
import sys
import glob
import traceback
from datetime import datetime

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
import config
from bot import script_gen, voiceover, visuals, editor, uploader

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
PRIVACY = os.getenv("YT_PRIVACY", "private").strip()
MAX_JOBS = int(os.getenv("MAX_JOBS", "3"))

_H = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


# ---------- tiny Supabase REST helpers ----------
def sb_get(path, **params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=_H, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_patch(path, data, **params):
    h = dict(_H, **{"Content-Type": "application/json", "Prefer": "return=minimal"})
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=h, params=params, json=data, timeout=30)
    r.raise_for_status()


def access_token_for(user_id: str) -> str:
    """Exchange the user's stored refresh token for a fresh access token."""
    rows = sb_get("channel_tokens", user_id=f"eq.{user_id}", select="refresh_token")
    if not rows:
        raise RuntimeError("no refresh token stored for this user (reconnect needed)")
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": rows[0]["refresh_token"],
        "grant_type": "refresh_token",
    })
    if r.status_code != 200:
        raise RuntimeError(f"token refresh failed: {r.text[:200]}")
    return r.json()["access_token"]


# ---------- build ----------
def _apply_language(lang: str):
    lang = (lang or "en").lower()
    config.LANG = lang
    config.VOICE = {"en": "en-US-AvaMultilingualNeural",
                    "hi": "hi-IN-SwaraNeural"}.get(lang, "en-US-AvaMultilingualNeural")


def recent_titles(user_id, limit=25):
    """The user's already-made video titles — so we never repeat a topic."""
    try:
        rows = sb_get("jobs", user_id=f"eq.{user_id}", title="not.is.null",
                      select="title", order="created_at.desc", limit=str(limit))
        return [r["title"] for r in rows if r.get("title")]
    except Exception:
        return []


def build_video(job, base, avoid_titles=None):
    cat = job.get("category") or ""
    sub = job.get("subcategory") or ""
    topic = sub or cat or "Amazing facts"
    field = f"{cat} > {sub}".strip(" >")
    ctx = (f"This faceless channel's fixed niche is '{field}'. Pick ONE fresh, specific, "
           f"fascinating idea strictly within this niche; vary it so videos never repeat.")
    if avoid_titles:
        ctx += (" Do NOT repeat or closely resemble any of these already-made videos: "
                + "; ".join(avoid_titles[:25]) + ". Choose a clearly different topic.")

    meta = script_gen.generate(topic, ctx)
    # STRICT safety gate — never auto-upload clearly unsafe content, whatever the niche.
    if not script_gen.is_safe(meta):
        raise RuntimeError("script failed safety check — skipped, not uploaded")
    vis, credits = visuals.get_scene_visuals(meta["scenes"], topic, base)
    scenes = []
    for i, (sc, (vp, vk)) in enumerate(zip(meta["scenes"], vis)):
        voice = f"{base}_s{i}_voice.mp3"
        words = voiceover.make_voiceover(sc["narration"], voice)
        scenes.append({
            "narration": sc["narration"], "narration_en": sc.get("narration_en", ""),
            "voice_path": voice, "visual_path": vp, "visual_kind": vk, "words": words,
        })
    out = base + ".mp4"
    editor.build_slideshow(scenes, out)
    return out, meta, credits


def _description(meta, credits):
    parts = [meta.get("description", ""), "", config.AI_DISCLOSURE, config.DISCLAIMER]
    if credits:
        uniq = list(dict.fromkeys(credits))
        parts += ["", "Image credits:"] + [f"- {c}" for c in uniq]
    return "\n".join(parts)


def _cleanup(base):
    for f in glob.glob(base + "*"):
        try:
            os.remove(f)
        except Exception:
            pass


def process(job):
    jid, uid = job["id"], job["user_id"]
    print(f"[worker] job {jid}: {job.get('category')} > {job.get('subcategory')} "
          f"(lang={job.get('language')})")
    sb_patch("jobs", {"status": "building"}, id=f"eq.{jid}")
    base = str(config.OUTPUT_DIR / f"job_{jid}")
    try:
        # get the user's access token FIRST -> fail fast if auth is broken (no wasted build)
        token = access_token_for(uid)
        _apply_language(job.get("language"))
        video, meta, credits = build_video(job, base, avoid_titles=recent_titles(uid))
        url = uploader.upload_with_token(video, meta["title"], _description(meta, credits),
                                         meta["tags"], token, PRIVACY)
        sb_patch("jobs", {"status": "done", "video_url": url, "title": meta["title"]}, id=f"eq.{jid}")
        print(f"[worker] job {jid} DONE -> {url}")
    except Exception as ex:
        traceback.print_exc()
        sb_patch("jobs", {"status": "error", "error": str(ex)[:500]}, id=f"eq.{jid}")
    finally:
        _cleanup(base)


def main():
    jobs = sb_get("jobs", status="eq.queued", order="created_at.asc", limit=str(MAX_JOBS))
    if not jobs:
        print("[worker] no queued jobs.")
        return
    print(f"[worker] {len(jobs)} job(s) to process at {datetime.now():%Y-%m-%d %H:%M}")
    for job in jobs:
        process(job)
    print("[worker] done.")


if __name__ == "__main__":
    main()
