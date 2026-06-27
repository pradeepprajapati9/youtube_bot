"""Daily faceless YouTube Shorts bot - full pipeline.

  trending -> scene script -> per-scene voiceover -> per-scene visuals
           -> multi-scene edit -> (upload)

Run daily via Windows Task Scheduler (run_daily.bat). With DO_UPLOAD=false it
just builds the video into output/ so you can review before publishing.
"""
import sys
import time
import traceback
from datetime import datetime

# Windows console defaults to cp1252; trending topics can contain non-ASCII
# (e.g. Hindi) text -> force UTF-8 so prints never crash the run.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from bot import thinker, trending, script_gen, voiceover, visuals, editor, uploader, analytics


def log(msg: str):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def cleanup():
    """After a successful upload, wipe all generated files and trim the log so
    storage never fills up. state.json (used-topics) is intentionally kept."""
    removed = 0
    for f in config.OUTPUT_DIR.glob("*"):
        try:
            f.unlink()
            removed += 1
        except Exception:
            pass
    # keep only the last 20 log lines
    try:
        lines = config.LOG_FILE.read_text("utf-8").splitlines()[-20:]
        config.LOG_FILE.write_text("\n".join(lines) + "\n", "utf-8")
    except Exception:
        pass
    print(f"[cleanup] removed {removed} files, trimmed log")


def run():
    t0 = time.time()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = str(config.OUTPUT_DIR / stamp)
    log(f"=== Run start (lang={config.LANG}, geo={config.TREND_GEO}, upload={config.DO_UPLOAD}) ===")

    # pre-clean: remove any leftovers from a previously failed run so output/ never piles up
    for f in config.OUTPUT_DIR.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass

    # 0. growth feedback: refresh stats of past uploads so the thinker can learn
    analytics.refresh_stats()

    # 1. thinker_bot picks the best ready idea (falls back to evergreen topics)
    thinker.top_up()
    idea = thinker.next_idea()
    if idea:
        topic = idea["title"]
        ctx = (f'Hook: {idea["hook"]}. Fresh original angle: {idea["angle"]}. '
               f'Psychology trigger: {idea["psychology"]}.')
    else:
        log("thinker has no ready idea (Gemini key missing?) -> evergreen fallback")
        topic, ctx = trending.pick_topic()
    log(f"Topic: {topic}")

    # 2. scene-based script
    meta = script_gen.generate(topic, ctx)
    log(f"Script: {len(meta['scenes'])} scenes | title: {meta['title']}")

    # 3. per-scene voiceover + 4. per-scene visual
    visuals_list, credits = visuals.get_scene_visuals(meta["scenes"], topic, base)
    scenes = []
    for i, (sc, (vpath, vkind)) in enumerate(zip(meta["scenes"], visuals_list)):
        voice_path = f"{base}_s{i}_voice.mp3"
        words = voiceover.make_voiceover(sc["narration"], voice_path)
        scenes.append({
            "narration": sc["narration"],
            "narration_en": sc.get("narration_en", ""),
            "voice_path": voice_path,
            "visual_path": vpath,
            "visual_kind": vkind,
            "words": words,
        })
    log(f"Built {len(scenes)} scenes (voice + visuals)")

    # 5. assemble multi-scene video
    video_path = base + ".mp4"
    editor.build_slideshow(scenes, video_path)
    log(f"Video built: {video_path}")

    # cross-promotion so every video feeds your other assets (one audience)
    promo = []
    if config.BLOG_URL:
        promo.append(f"📚 Free tips, guides & calculators: {config.BLOG_URL}")
    if config.TELEGRAM_URL:
        promo.append(f"💬 Daily deals on Telegram: {config.TELEGRAM_URL}")
    promo.append("🔔 Subscribe for daily videos!")

    # build a compliance-safe description (cross-promo + disclosure + disclaimer + credits)
    desc_parts = [meta["description"], ""] + promo + ["", config.AI_DISCLOSURE, config.DISCLAIMER]
    if credits:
        uniq = list(dict.fromkeys(credits))   # de-dupe, keep order
        desc_parts += ["", "Image credits:"] + [f"- {c}" for c in uniq]
    full_description = "\n".join(desc_parts)

    # mark this idea/topic as used so it's never produced again
    if idea:
        thinker.mark_used(idea["id"])
    trending.mark_used(topic)

    # 6. upload (optional)
    if config.DO_UPLOAD:
        url = uploader.upload(video_path, meta["title"], full_description, meta["tags"])
        log(f"Uploaded: {url}")
        analytics.record_upload(url.rstrip("/").split("/")[-1], idea, meta["title"])

        # cross-post to Instagram Reels (optional; never breaks the YouTube flow)
        try:
            from bot import instagram
            ig_caption = f'{meta["title"]}\n\n#reels #fyp #viral #facts #shorts'
            rid = instagram.post_reel(video_path, ig_caption)
            if rid:
                log(f"Instagram reel: {rid}")
        except Exception as ex:
            log(f"Instagram skipped: {ex}")

        log(f"=== Done in {time.time() - t0:.0f}s ===")
        if config.CLEAN_AFTER_UPLOAD:
            cleanup()   # wipe files/log AFTER logging the success
    else:
        log("DO_UPLOAD=false -> skipped upload (review the video, then set DO_UPLOAD=true).")
        log(f"=== Done in {time.time() - t0:.0f}s ===")
    return video_path


if __name__ == "__main__":
    try:
        run()
    except Exception:
        log("ERROR:\n" + traceback.format_exc())
        sys.exit(1)
