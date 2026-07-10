"""Upload the finished Short to YouTube via the Data API v3 (FREE).

One-time setup (see README):
  1. Create a Google Cloud project, enable 'YouTube Data API v3'.
  2. Create OAuth client (Desktop app), download as credentials/client_secret.json
  3. First run opens a browser to authorize -> token saved to credentials/token.json
"""
import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if config.TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), SCOPES)
        except Exception as ex:
            print(f"[upload] token.json unreadable ({ex}); will re-authorize.")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not config.CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {config.CLIENT_SECRET_FILE}. Add your OAuth client_secret.json "
                    "(see README) before enabling uploads."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        config.TOKEN_FILE.write_text(creds.to_json(), "utf-8")
    return build("youtube", "v3", credentials=creds)


def upload_with_token(video_path: str, title: str, description: str,
                      tags: list[str], access_token: str, privacy: str = "private") -> str:
    """Upload to the channel that OWNS `access_token` (multi-user worker path).

    Unlike upload(), this does NOT use the local token.json OAuth flow — it uses
    a per-user OAuth access token (minted from that user's stored refresh token),
    so each user's video lands on THEIR OWN channel.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(token=access_token)
    youtube = build("youtube", "v3", credentials=creds)
    # YouTube rejects titles/descriptions containing < or > (invalidDescription/Title).
    clean = lambda s: (s or "").replace("<", "(").replace(">", ")")
    body = {
        "snippet": {
            "title": clean(title)[:100],
            "description": clean(description)[:4900],
            "tags": tags[:15],
            "categoryId": "27",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"[upload] {int(status.progress() * 100)}%")
    url = f"https://youtu.be/{resp['id']}"
    print(f"[upload] done -> {url}")
    return url


def upload(video_path: str, title: str, description: str, tags: list[str]) -> str:
    from googleapiclient.http import MediaFileUpload

    youtube = _get_service()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:15],
            "categoryId": "27",  # Education; change as you like
        },
        "status": {
            "privacyStatus": config.YT_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"[upload] {int(status.progress() * 100)}%")
    vid = resp["id"]
    url = f"https://youtu.be/{vid}"
    print(f"[upload] done -> {url}")
    return url
