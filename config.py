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
LOG_FILE = BASE_DIR / "bot.log"

for d in (OUTPUT_DIR, ASSETS_DIR, CRED_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- user settings ---
# NOTE: use VIDEO_LANG (not LANG) - on Linux/CI, LANG is a reserved system env var.
LANG = os.getenv("VIDEO_LANG", "en").lower()
TREND_GEO = os.getenv("TREND_GEO", "IN").upper()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
YT_PRIVACY = os.getenv("YT_PRIVACY", "private").strip()
DO_UPLOAD = os.getenv("DO_UPLOAD", "false").lower() == "true"
# After a successful upload, wipe generated files + trim the log so storage
# never grows. Only the tiny state.json (used-topics) is kept.
CLEAN_AFTER_UPLOAD = os.getenv("CLEAN_AFTER_UPLOAD", "true").lower() == "true"

# --- video format (YouTube Shorts: vertical, <= 60s) ---
WIDTH, HEIGHT = 1080, 1920
FPS = 24                  # 24 is plenty for Shorts and ~20% faster to render
MAX_SECONDS = 58          # keep under 60s so YouTube treats it as a Short
TARGET_WORDS = 140        # ~ enough narration for ~55s at a natural pace

# Neural TTS voices per language (edge-tts, free)
VOICE = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
}.get(LANG, "en-US-AriaNeural")

# Font for captions (Windows built-in). Falls back handled in editor.py
FONT_PATH = r"C:\Windows\Fonts\arialbd.ttf"

# YouTube OAuth files
CLIENT_SECRET_FILE = CRED_DIR / "client_secret.json"
TOKEN_FILE = CRED_DIR / "token.json"
