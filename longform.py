"""Weekly LONG-FORM YouTube video bot - reuses the Shorts pipeline.

Why: regular (non-Shorts) videos monetize far better than Shorts (real ad
breaks, higher RPM). This builds ONE 4-7 minute "N mind-blowing facts about X"
video using the SAME script -> voiceover -> visuals -> editor modules, then
optionally uploads it as a normal video (no #Shorts, so YouTube treats it as
long-form). Same channel, same OAuth credentials as the Shorts bot.

Run:
  python longform.py                 -> build only (review in output/)
  DO_UPLOAD=true python longform.py  -> build + upload

Tunables (env): LONGFORM_FACTS (default 12), LONGFORM_MAX_SEC (default 600).
"""
import os
import sys
import json
import time
import traceback
from datetime import datetime

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from bot import thinker, voiceover, visuals, editor, uploader

STATE_FILE = config.BASE_DIR / "longform_state.json"      # used themes (avoid repeats)
N_FACTS = int(os.getenv("LONGFORM_FACTS", "12"))
MAX_SEC = float(os.getenv("LONGFORM_MAX_SEC", "600"))      # hard ceiling (~10 min)


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [longform] {msg}"
    print(line)
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _used_themes():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8")).get("themes", [])
        except Exception:
            pass
    return []


def _mark_theme(theme: str):
    themes = _used_themes()
    themes.append(theme.lower().strip())
    STATE_FILE.write_text(json.dumps({"themes": themes[-60:]}, ensure_ascii=False, indent=2),
                          "utf-8")


def _gen_script(avoid: list[str]):
    """Ask Gemini for a full long-form script. Returns dict or None."""
    lang = "Hindi" if config.LANG == "hi" else "English"
    avoid_s = "; ".join(avoid[-30:]) or "none yet"
    prompt = (
        f"You are a top faceless YouTube creator scripting a {N_FACTS}-fact "
        f"LONG-FORM video (4-7 minutes) in {lang}. Pick ONE broadly-appealing, "
        f"SAFE, fascinating theme (space, deep ocean, the human body, history "
        f"mysteries, animals, psychology, money, the universe...). Do NOT reuse "
        f"these recent themes: {avoid_s}.\n"
        f"Goal: maximum watch-time + subscribes + comments using curiosity, awe "
        f"and surprise. Return ONLY valid JSON, no markdown, exact shape:\n"
        f'{{"theme": "...", "title": "...", "description": "...", '
        f'"tags": ["..."], "scenes": [{{"narration": "...", "keyword": "..."}}]}}\n'
        f"RULES:\n"
        f"- First scene = a powerful 1-2 sentence HOOK that makes viewers stay "
        f"(promise the most shocking fact is coming).\n"
        f"- Then exactly {N_FACTS} fact scenes, each 2-4 spoken sentences, "
        f"vivid and SPECIFIC, escalating curiosity; save the most jaw-dropping "
        f"fact for last.\n"
        f"- Final scene = recap the wow, then ask an easy fun QUESTION (drives "
        f"comments) and a clear SUBSCRIBE call-to-action.\n"
        f"- 'keyword' per scene = 2-3 ENGLISH words for a matching stock clip "
        f"(always English, even for Hindi narration).\n"
        f"- title in {lang}, accurate + curiosity-driving, under 90 chars, "
        f"NO '#Shorts' (this is a long video). narration, title, description "
        f"all in {lang}.\n"
        f"SAFETY: only well-established verifiable facts; no made-up statistics, "
        f"no medical/financial/legal advice, no defamation, no graphic content."
    )
    raw = thinker.gemini_call(prompt, timeout=90)
    if not raw:
        return None
    try:
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        data = json.loads(raw)
        if data.get("scenes"):
            return data
    except Exception as ex:
        log(f"script JSON parse failed: {ex}")
    return None


def run():
    t0 = time.time()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = str(config.OUTPUT_DIR / f"longform_{stamp}")
    log(f"=== Run start (lang={config.LANG}, facts={N_FACTS}, upload={config.DO_UPLOAD}) ===")

    data = _gen_script(_used_themes())
    if not data:
        log("Gemini script generation failed (key missing/overloaded). Aborting.")
        return None

    theme = data.get("theme", "facts")
    title = (data.get("title") or f"{N_FACTS} Amazing Facts").strip()[:100]
    scenes_in = [s for s in data["scenes"] if s.get("narration")]
    log(f"Theme: {theme} | title: {title} | {len(scenes_in)} scenes")

    # build per-scene visuals + voiceovers (same pipeline as Shorts)
    visuals_list, credits = visuals.get_scene_visuals(scenes_in, theme, base)
    scenes = []
    for i, (sc, (vpath, vkind)) in enumerate(zip(scenes_in, visuals_list)):
        voice_path = f"{base}_s{i}_voice.mp3"
        words = voiceover.make_voiceover(sc["narration"], voice_path)
        scenes.append({
            "narration": sc["narration"],
            "voice_path": voice_path,
            "visual_path": vpath,
            "visual_kind": vkind,
            "words": words,
        })
    log(f"Built {len(scenes)} scenes (voice + visuals)")

    video_path = base + ".mp4"
    editor.build_slideshow(scenes, video_path, max_seconds=MAX_SEC)
    log(f"Video built: {video_path}")

    # cross-promotion + compliance (same funnel as the Shorts)
    promo = []
    if config.BLOG_URL:
        promo.append(f"📚 Free tips, guides & calculators: {config.BLOG_URL}")
    if config.TELEGRAM_URL:
        promo.append(f"💬 Daily deals on Telegram: {config.TELEGRAM_URL}")
    promo.append("🔔 Subscribe for more!")
    desc_parts = [data.get("description", title), ""] + promo + \
                 ["", config.AI_DISCLOSURE, config.DISCLAIMER]
    if credits:
        uniq = list(dict.fromkeys(credits))
        desc_parts += ["", "Image credits:"] + [f"- {c}" for c in uniq]
    full_description = "\n".join(desc_parts)

    tags = list(dict.fromkeys((data.get("tags") or []) +
                              ["facts", "education", "amazing", "didyouknow"]))[:15]

    _mark_theme(theme)

    if config.DO_UPLOAD:
        url = uploader.upload(video_path, title, full_description, tags)
        log(f"Uploaded: {url}")
        # clean this run's files (keep longform_state.json)
        if config.CLEAN_AFTER_UPLOAD:
            removed = 0
            for f in config.OUTPUT_DIR.glob(f"longform_{stamp}*"):
                try:
                    f.unlink(); removed += 1
                except Exception:
                    pass
            log(f"cleanup: removed {removed} files")
    else:
        log("DO_UPLOAD=false -> built only (review the video, then set DO_UPLOAD=true).")
    log(f"=== Done in {time.time() - t0:.0f}s ===")
    return video_path


if __name__ == "__main__":
    try:
        run()
    except Exception:
        log("ERROR:\n" + traceback.format_exc())
        sys.exit(1)
