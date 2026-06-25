"""Fetch a visual for each scene - FREE.

Priority per scene:
  1. Pexels portrait VIDEO     (only if PEXELS_API_KEY set) -> best
  2. Openverse / Wikimedia IMAGE (no key needed)            -> real scenes
  3. Auto gradient image                                    -> always works
Returns list of (path, kind) where kind in {"video","image"}.
"""
import io
import random
import requests
from PIL import Image, ImageFilter
import config

UA = {"User-Agent": "yt-bot/1.0 (educational)"}


# ---------- Pexels video (optional, needs free key) ----------
def _pexels_video(query: str, out_path: str):
    if not config.PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "orientation": "portrait", "per_page": 8, "size": "medium"},
            timeout=25,
        )
        if r.status_code != 200:
            return None
        vids = r.json().get("videos", [])
        if not vids:
            return None
        vid = random.choice(vids)
        files = sorted(vid["video_files"], key=lambda f: abs((f.get("height") or 0) - 1920))
        data = requests.get(files[0]["link"], timeout=60).content
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path
    except Exception as ex:
        print(f"[visuals] pexels failed: {ex}")
        return None


# ---------- No-key image sources ----------
def _openverse_many(query: str, n: int = 8):
    """Return up to n reliable thumbnail URLs for a query."""
    urls = []
    try:
        r = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": n, "license_type": "all"},
            timeout=20, headers=UA,
        )
        if r.status_code == 200:
            for res in r.json().get("results", []):
                # 'thumbnail' is Openverse's own CDN (reliable); raw 'url' often 403s.
                u = res.get("thumbnail") or res.get("url")
                if u:
                    urls.append(u)
    except Exception as ex:
        print(f"[visuals] openverse failed: {ex}")
    return urls


def _wikimedia_many(query: str, n: int = 8):
    urls = []
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6,
                "gsrlimit": n, "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 1080,
            },
            timeout=20, headers=UA,
        )
        if r.status_code == 200:
            pages = (r.json().get("query") or {}).get("pages", {})
            for p in pages.values():
                ii = p.get("imageinfo")
                if ii:
                    u = ii[0].get("thumburl") or ii[0].get("url")
                    if u:
                        urls.append(u)
    except Exception as ex:
        print(f"[visuals] wikimedia failed: {ex}")
    return urls


def _download_image(url: str, out_path: str):
    try:
        data = requests.get(url, timeout=30, headers=UA).content
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img = _to_vertical(img)
        img.save(out_path, "PNG")
        return out_path
    except Exception as ex:
        print(f"[visuals] image download failed: {ex}")
        return None


def _to_vertical(img: Image.Image) -> Image.Image:
    """Cover-fit to 1080x1920 with a blurred fill so nothing is stretched."""
    W, H = config.WIDTH, config.HEIGHT
    # blurred background fill
    bg = img.copy()
    scale = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * scale), int(bg.height * scale)))
    left = (bg.width - W) // 2
    top = (bg.height - H) // 2
    bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(30))
    # foreground fit-inside
    fg = img.copy()
    fscale = min(W / fg.width, H / fg.height)
    fg = fg.resize((int(fg.width * fscale), int(fg.height * fscale)))
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return bg


def _gradient(seed: str, out_path: str):
    random.seed(sum(ord(c) for c in seed) or 1)
    W, H = config.WIDTH, config.HEIGHT
    top = tuple(random.randint(20, 90) for _ in range(3))
    bot = tuple(random.randint(10, 60) for _ in range(3))
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        px_row = tuple(int(top[k] * (1 - t) + bot[k] * t) for k in range(3))
        for x in range(W):
            px[x, y] = px_row
    img.save(out_path)
    return out_path


def get_scene_visuals(scenes: list[dict], topic: str, base: str) -> list[tuple[str, str]]:
    """Return a (path, kind) per scene.

    Images are pulled from a per-query pool so each scene gets a DIFFERENT but
    relevant picture. The topic is used as a fallback query so scenes stay on-topic
    even when a scene's own keyword is weak.
    """
    out = []
    pools: dict[str, list[str]] = {}   # query -> remaining urls (consumed in order)

    def pool_for(q: str):
        if q not in pools:
            pools[q] = _openverse_many(q, 8) or _wikimedia_many(q, 8)
        return pools[q]

    for i, sc in enumerate(scenes):
        kw = (sc.get("keyword") or "").strip()
        query = kw if len(kw) >= 4 else topic
        p_base = f"{base}_s{i}"

        # 1) Pexels video if key present
        vp = p_base + ".mp4"
        if _pexels_video(query, vp):
            print(f"[visuals] scene {i}: pexels video ({query})")
            out.append((vp, "video"))
            continue

        # 2) free image - try the scene's query pool, then the topic pool
        ip = p_base + ".png"
        done = False
        for q in (query, topic):
            urls = pool_for(q)
            while urls:
                url = urls.pop(0)
                if _download_image(url, ip):
                    print(f"[visuals] scene {i}: image ({q})")
                    out.append((ip, "image"))
                    done = True
                    break
            if done:
                break
        if done:
            continue

        # 3) gradient fallback
        _gradient(query + str(i), ip)
        print(f"[visuals] scene {i}: gradient fallback")
        out.append((ip, "image"))
    return out
