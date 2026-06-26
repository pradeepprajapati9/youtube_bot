"""Cross-post the generated Short to Instagram Reels via the Graph API (free).

Doubles your reach for free by reusing the same video. No-op unless both
IG_USER_ID and IG_ACCESS_TOKEN are configured (see README for one-time setup).

Flow: host the mp4 at a public URL -> create a REELS media container ->
poll until processed -> publish.
"""
import time
import requests
import config

# graph.instagram.com (Instagram Login, no Facebook Page) by default.
GRAPH = config.IG_API_BASE


def _host_video(video_path: str):
    """Upload to a free transient host (catbox.moe) -> public direct URL.
    Instagram needs a public video_url it can fetch."""
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": f}, timeout=180,
            )
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
        print(f"[instagram] host upload failed: {r.status_code} {r.text[:100]}")
    except Exception as ex:
        print(f"[instagram] host upload error: {ex}")
    return None


def post_reel(video_path: str, caption: str):
    """Publish video_path as an Instagram Reel. Returns the media id or None."""
    if not (config.IG_USER_ID and config.IG_ACCESS_TOKEN):
        return None
    video_url = _host_video(video_path)
    if not video_url:
        return None
    try:
        # 1) create the REELS container
        r = requests.post(f"{GRAPH}/{config.IG_USER_ID}/media", timeout=60, data={
            "media_type": "REELS", "video_url": video_url,
            "caption": caption[:2200], "access_token": config.IG_ACCESS_TOKEN,
        })
        cid = r.json().get("id")
        if not cid:
            print(f"[instagram] container failed: {r.text[:200]}")
            return None

        # 2) wait for Instagram to finish processing the video
        for _ in range(25):
            time.sleep(6)
            s = requests.get(f"{GRAPH}/{cid}", timeout=30, params={
                "fields": "status_code", "access_token": config.IG_ACCESS_TOKEN})
            code = s.json().get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                print("[instagram] processing ERROR")
                return None
        else:
            print("[instagram] processing timed out")
            return None

        # 3) publish
        p = requests.post(f"{GRAPH}/{config.IG_USER_ID}/media_publish", timeout=60, data={
            "creation_id": cid, "access_token": config.IG_ACCESS_TOKEN})
        pid = p.json().get("id")
        if pid:
            print(f"[instagram] reel published: {pid}")
            return pid
        print(f"[instagram] publish failed: {p.text[:200]}")
    except Exception as ex:
        print(f"[instagram] post error: {ex}")
    return None
