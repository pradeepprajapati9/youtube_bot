"""Central configuration. Reads .env (if present) with safe defaults."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass  # dotenv optional; env vars still work

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
CRED_DIR = BASE_DIR / "credentials"
STATE_FILE = BASE_DIR / "state.json"      # remembers used topics (avoid repeats)
BACKLOG_FILE = BASE_DIR / "backlog.json"  # thinker_bot's pre-thought video ideas
PERF_FILE = BASE_DIR / "performance.json" # per-video stats -> growth feedback loop
LOG_FILE = BASE_DIR / "bot.log"

for d in (OUTPUT_DIR, ASSETS_DIR, CRED_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- user settings ---
# NOTE: use VIDEO_LANG (not LANG) - on Linux/CI, LANG is a reserved system env var.
LANG = os.getenv("VIDEO_LANG", "en").lower()
TREND_GEO = os.getenv("TREND_GEO", "IN").upper()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# YouTube Data API key (just an API key, NOT OAuth) for reading public video
# stats -> powers the growth feedback loop. Optional; loop is dormant without it.
YT_API_KEY = os.getenv("YT_API_KEY", "").strip()
YT_PRIVACY = os.getenv("YT_PRIVACY", "private").strip()
DO_UPLOAD = os.getenv("DO_UPLOAD", "false").lower() == "true"
# After a successful upload, wipe generated files + trim the log so storage
# never grows. Only the tiny state.json (used-topics) is kept.
CLEAN_AFTER_UPLOAD = os.getenv("CLEAN_AFTER_UPLOAD", "true").lower() == "true"

# Content mode: "evergreen" (safe factual topics - lowest policy risk) or
# "trending" (today's Google Trends, blocklist-filtered).
CONTENT_MODE = os.getenv("CONTENT_MODE", "evergreen").lower()

# --- thinker_bot (growth brain) ---
# The thinker is a GROWTH STRATEGIST, not a fixed-topic generator. It uses the
# psychology of virality + human interest to pick WHATEVER kind of video will
# grow a new faceless channel fastest (any topic, as long as it's safe & original).
NICHE = os.getenv("NICHE", "Viral curiosity content (growth-first, any topic)")
NICHE_DESC = os.getenv(
    "NICHE_DESC",
    "any high-reach, broadly-appealing, SAFE content for a fast-growing faceless "
    "channel - e.g. mind-blowing facts, did-you-know curiosities, science & space "
    "wonders, psychology & human behaviour, history surprises, incredible nature, "
    "animals and places, oddly-fascinating phenomena. Pick whatever maximises reach.",
)
# Keep at least this many unused ideas queued; refill in batches of this size.
BACKLOG_MIN = int(os.getenv("BACKLOG_MIN", "8"))
IDEAS_PER_REFILL = int(os.getenv("IDEAS_PER_REFILL", "10"))
# Only produce ideas scoring >= this (virality+originality, 0-100). Spam guard.
QUALITY_THRESHOLD = int(os.getenv("QUALITY_THRESHOLD", "62"))

# --- Compliance text auto-added to every video description ---
AI_DISCLOSURE = "Note: This video uses AI-generated narration."
DISCLAIMER = "Disclaimer: For educational and entertainment purposes only."

# --- video format (YouTube Shorts: vertical, <= 60s) ---
WIDTH, HEIGHT = 1080, 1920
FPS = 24                  # 24 is plenty for Shorts and ~20% faster to render
MAX_SECONDS = 58          # keep under 60s so YouTube treats it as a Short
TARGET_WORDS = 140        # ~ enough narration for ~55s at a natural pace

# Neural TTS voices per language (edge-tts, free). Multilingual voices sound
# noticeably more natural/engaging than the older "Aria".
VOICE = {
    "en": "en-US-AvaMultilingualNeural",
    "hi": "hi-IN-SwaraNeural",
}.get(LANG, "en-US-AvaMultilingualNeural")
# Slightly faster = more energetic, better for Shorts retention.
VOICE_RATE = os.getenv("VOICE_RATE", "+6%")

# Font for captions (Windows built-in). Falls back handled in editor.py
FONT_PATH = r"C:\Windows\Fonts\arialbd.ttf"

# YouTube OAuth files
CLIENT_SECRET_FILE = CRED_DIR / "client_secret.json"
TOKEN_FILE = CRED_DIR / "token.json"
