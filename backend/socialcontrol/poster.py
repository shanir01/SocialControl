"""Auto-post: YouTube (Data API, OAuth), Instagram Reels (Graph API, resumable upload), Pinterest (own video pin, optional).
Also the YouTube edit helpers Full Control uses in API mode (recommended, ToS-safe path)."""
from __future__ import annotations
import json, os, time
from . import config
from .http import req, ProviderError

YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl",
             "https://www.googleapis.com/auth/youtube.readonly"]
TOKEN = config.DATA / "yt_token.json"

def yt_service(interactive=True):
    """OAuth: opens Google's own sign-in page in your browser once; token saved in data/yt_token.json (never committed).
    In GitHub Actions put the token JSON in the YT_TOKEN_JSON secret."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = None
    if os.environ.get("YT_TOKEN_JSON"):
        creds = Credentials.from_authorized_user_info(json.loads(os.environ["YT_TOKEN_JSON"]), YT_SCOPES)
    elif TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), YT_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise ProviderError("YouTube not connected — Settings → 'Connect YouTube'")
        from google_auth_oauthlib.flow import InstalledAppFlow
        sec = config.key("YT_CLIENT_SECRET_FILE") or str(config.ROOT / "client_secret.json")
        if not os.path.exists(sec):
            raise ProviderError(f"client_secret.json not found at {sec}")
        creds = InstalledAppFlow.from_client_secrets_file(sec, YT_SCOPES).run_local_server(port=0)
    if not os.environ.get("YT_TOKEN_JSON"):
        TOKEN.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)

def yt_connected() -> bool:
    return TOKEN.exists() or bool(os.environ.get("YT_TOKEN_JSON"))

def youtube_upload(path, title, description, tags, privacy="private", made_for_kids=False) -> dict:
    from googleapiclient.http import MediaFileUpload
    yt = yt_service(interactive=False)
    body = {"snippet": {"title": title[:100], "description": description[:4900], "tags": tags[:30], "categoryId": "28"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": made_for_kids}}
    r = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(path, chunksize=-1, resumable=True)).execute()
    return {"platform": "youtube", "id": r["id"], "url": f"https://youtube.com/shorts/{r['id']}"}

def yt_my_videos(limit=50) -> list[dict]:
    yt = yt_service(interactive=False)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]; ids, tok = [], None
    while len(ids) < limit:
        r = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]; tok = r.get("nextPageToken")
        if not tok: break
    out = []
    for i in range(0, len(ids[:limit]), 50):
        r = yt.videos().list(part="snippet,statistics,status", id=",".join(ids[i:i+50])).execute()
        for v in r["items"]:
            out.append({"id": v["id"], "title": v["snippet"]["title"], "description": v["snippet"].get("description", ""),
                        "tags": v["snippet"].get("tags", []), "categoryId": v["snippet"].get("categoryId", "22"),
                        "views": int(v["statistics"].get("viewCount", 0)), "privacy": v["status"]["privacyStatus"]})
    return out

def yt_update_video(video_id, title=None, description=None, tags=None, category_id=None, made_for_kids=None) -> dict:
    yt = yt_service(interactive=False)
    v = yt.videos().list(part="snippet,status", id=video_id).execute()["items"][0]
    sn, st = v["snippet"], v["status"]
    if title: sn["title"] = title[:100]
    if description is not None: sn["description"] = description[:4900]
    if tags is not None: sn["tags"] = tags[:30]
    if category_id: sn["categoryId"] = str(category_id)
    body = {"id": video_id, "snippet": {k: sn[k] for k in ("title", "description", "tags", "categoryId") if k in sn}}
    parts = "snippet"
    if made_for_kids is not None:
        body["status"] = {"privacyStatus": st["privacyStatus"], "selfDeclaredMadeForKids": bool(made_for_kids)}; parts += ",status"
    yt.videos().update(part=parts, body=body).execute()
    return {"ok": True, "id": video_id}

def yt_unreplied_comments(video_id, limit=20) -> list[dict]:
    yt = yt_service(interactive=False)
    r = yt.commentThreads().list(part="snippet", videoId=video_id, maxResults=min(limit, 100), order="time").execute()
    out = []
    for t in r.get("items", []):
        if t["snippet"].get("totalReplyCount", 0) == 0:
            c = t["snippet"]["topLevelComment"]
            out.append({"id": c["id"], "text": c["snippet"]["textOriginal"], "author": c["snippet"].get("authorDisplayName")})
    return out

def yt_reply(comment_id, text) -> dict:
    yt = yt_service(interactive=False)
    r = yt.comments().insert(part="snippet", body={"snippet": {"parentId": comment_id, "textOriginal": text[:900]}}).execute()
    return {"ok": True, "id": r["id"]}

GRAPH = "https://graph.facebook.com/v21.0"

def instagram_reel(path, caption) -> dict:
    """Reels publish with resumable upload from your PC (no public URL needed)."""
    tok, uid = config.key("IG_ACCESS_TOKEN"), config.key("IG_USER_ID")
    if not (tok and uid): raise ProviderError("IG_ACCESS_TOKEN / IG_USER_ID missing")
    c = req("POST", f"{GRAPH}/{uid}/media", data={"media_type": "REELS", "upload_type": "resumable", "caption": caption[:2100],
            "share_to_feed": "true", "access_token": tok}).json()
    cid = c["id"]; size = os.path.getsize(path)
    with open(path, "rb") as f:
        req("POST", c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v21.0/{cid}", data=f, timeout=600,
            headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)})
    for _ in range(60):
        s = req("GET", f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": tok}).json()
        if s.get("status_code") == "FINISHED": break
        if s.get("status_code") == "ERROR": raise ProviderError(f"instagram processing error: {s}")
        time.sleep(5)
    p = req("POST", f"{GRAPH}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}).json()
    link = req("GET", f"{GRAPH}/{p['id']}", params={"fields": "permalink", "access_token": tok}).json().get("permalink")
    return {"platform": "instagram", "id": p["id"], "url": link}

def pinterest_video_pin(path, title, description) -> dict:
    """Post YOUR OWN video as a Pin (Pinterest API v5). Optional."""
    tok, board = config.key("PINTEREST_ACCESS_TOKEN"), config.key("PINTEREST_BOARD_ID")
    if not (tok and board): raise ProviderError("PINTEREST_ACCESS_TOKEN / PINTEREST_BOARD_ID missing")
    h = {"Authorization": f"Bearer {tok}"}
    m = req("POST", "https://api.pinterest.com/v5/media", headers=h, json={"media_type": "video"}).json()
    with open(path, "rb") as f:
        req("POST", m["upload_url"], data=m["upload_parameters"], files={"file": f}, timeout=600)
    for _ in range(60):
        s = req("GET", f"https://api.pinterest.com/v5/media/{m['media_id']}", headers=h).json()
        if s.get("status") == "succeeded": break
        if s.get("status") == "failed": raise ProviderError(f"pinterest media failed: {s}")
        time.sleep(5)
    pin = req("POST", "https://api.pinterest.com/v5/pins", headers=h, json={"board_id": board, "title": title[:100],
              "description": description[:500], "media_source": {"source_type": "video_id", "media_id": m["media_id"], "cover_image_key_frame_time": 1}}).json()
    return {"platform": "pinterest", "id": pin["id"], "url": f"https://www.pinterest.com/pin/{pin['id']}/"}
