# 🤖 Daily YouTube Shorts Bot (Python, free stack)

Automatically: picks a **trending topic** → writes a **script** → makes a **voiceover** →
grabs a **background** → edits a **vertical Short** → **uploads to YouTube** — once a day.

Everything uses **free** tools (edge-tts, Wikipedia, Google Trends, ffmpeg). Two optional
free signups improve quality (Pexels footage, Gemini scripts) and one is required to upload
(YouTube OAuth — also free).

---

## 1. Install

```powershell
cd c:\xampp\htdocs\laravel_project\youtube_bot
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

ffmpeg is bundled via `imageio-ffmpeg` — no separate install needed.

## 2. Configure

```powershell
copy .env.example .env
```

Edit `.env`:
- `LANG=en` or `hi`
- `TREND_GEO=IN` (or US, GB…)
- `PEXELS_API_KEY=` — optional, free key from https://www.pexels.com/api/ (nicer footage)
- `GEMINI_API_KEY=` — optional, free key from https://aistudio.google.com/apikey (smarter scripts)
- `DO_UPLOAD=false` — keep **false** first to test; switch to `true` when happy
- `YT_PRIVACY=private` — switch to `public` once you trust the output

## 3. Test (no upload)

```powershell
venv\Scripts\python.exe main.py
```

Check the generated `.mp4` inside `output\`. Tweak voice/captions if needed.

## 4. Enable YouTube upload (one-time OAuth)

1. Go to https://console.cloud.google.com/ → create a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → Credentials** → *Create credentials* → **OAuth client ID** →
   application type **Desktop app** → download the JSON.
4. Save it as `credentials\client_secret.json`.
5. Set `DO_UPLOAD=true` in `.env`, then run `python main.py` once — a browser opens to
   authorize. The token is cached in `credentials\token.json` for all future runs.

> Quota note: default YouTube API quota = 10,000 units/day; one upload ≈ 1,600 units →
> up to ~6 uploads/day. Daily 1 video is well within limits.

## 5. Schedule it daily (Windows Task Scheduler)

1. Open **Task Scheduler** → *Create Basic Task*.
2. Trigger: **Daily**, pick a time (e.g. 9:00 AM).
3. Action: **Start a program** → Program: `run_daily.bat`
   (Start in: this folder's full path).
4. Finish. The bot now runs every day automatically.

(Equivalent to a Linux cronjob `0 9 * * *`.)

---

## ☁️ Run in the cloud daily (GitHub Actions — no PC needed)

`.github/workflows/daily.yml` runs the bot on GitHub's servers every day (cron) and
gives you a manual **Run workflow** button. Your computer can stay off.

**One-time setup — add 3 repo Secrets** (repo → *Settings → Secrets and variables → Actions → New repository secret*):

| Secret name | Value |
|-------------|-------|
| `GEMINI_API_KEY` | your Gemini key (from `.env`) |
| `YT_CLIENT_SECRET` | paste the **entire contents** of `credentials/client_secret.json` |
| `YT_TOKEN` | paste the **entire contents** of `credentials/token.json` |
| `PEXELS_API_KEY` | *(optional)* your Pexels key, or leave unset |

Then: repo → **Actions** tab → enable workflows → open *Daily YouTube Short* → **Run workflow**
to test. After that it runs automatically on the cron schedule (default 02:00 IST).

> The workflow installs ffmpeg+fonts, restores your secrets to files at runtime, makes the
> video, uploads it, then commits the updated `state.json` back so topics never repeat.

## ♻️ Self-cleaning (storage never fills)

After every **successful upload**, the bot wipes `output/` (all videos/images/audio) and
trims `bot.log` to the last 20 lines. Only the tiny `state.json` (used-topic list) survives.
So nothing piles up — locally or in CI. Controlled by `CLEAN_AFTER_UPLOAD=true` in `.env`.
(There is **no database** — the bot is fully file-based.)

---

## How it stays compliant & gets views
- **Vertical 1080×1920, < 60s, `#Shorts`** in title → YouTube treats it as a Short.
- Captions are burned in (most Shorts are watched on mute) → better watch-time.
- Topics come from real trending demand → higher chance of views.
- `state.json` remembers used topics so videos don't repeat.
- `selfDeclaredMadeForKids=False` and Education category set by default.

⚠️ Keep content original/transformative and accurate. Pure reposting or low-effort spam
can fail YouTube monetization review — the script step is where you raise quality (add a
Gemini key, or edit `bot/script_gen.py`).

## File map
```
main.py              orchestrates the daily run
config.py            settings (reads .env)
bot/trending.py      Google Trends -> topic
bot/script_gen.py    topic -> narration (Gemini / Wikipedia / template)
bot/voiceover.py     edge-tts -> mp3
bot/visuals.py       Pexels video / gradient background
bot/editor.py        moviepy -> final vertical mp4
bot/uploader.py      YouTube Data API upload
run_daily.bat        Task Scheduler entry point
output/              generated videos + assets
```
