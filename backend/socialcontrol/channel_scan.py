"""Scan any YouTube channel (handle/URL): all videos + views, bucket them (100+, 200+ ... 1M+), find top topics.
With YOUTUBE_API_KEY uses the official API; without a key falls back to yt-dlp (public listing)."""
from __future__ import annotations
import json, re, shutil, subprocess
from collections import Counter, defaultdict
from . import config
from .http import req, ProviderError
from .textutil import keywords

THRESHOLDS = [100, 200, 300, 400, 500, 1_000, 10_000, 100_000, 1_000_000, 10_000_000]

def label(n: int) -> str:
    return f"{n // 1_000_000}M+" if n >= 1_000_000 else f"{n // 1000}K+" if n >= 1000 else f"{n}+"

def bucket_of(views: int) -> str:
    b = None
    for t in THRESHOLDS:
        if views >= t:
            b = t
    return label(b) if b is not None else "<100"

def bucketize(videos: list[dict]) -> dict:
    """Returns {bucket_label: count} in threshold order plus cumulative 'X+' counts (a 1K video is also 100+ ... 500+)."""
    exact = defaultdict(int); cumulative = {}
    for v in videos:
        exact[bucket_of(v["views"])] += 1
    for t in THRESHOLDS:
        cumulative[label(t)] = sum(1 for v in videos if v["views"] >= t)
    order = ["<100"] + [label(t) for t in THRESHOLDS]
    return {"exact": {k: exact.get(k, 0) for k in order}, "cumulative": cumulative}

def top_topics(videos: list[dict], top_share=0.25, n=12) -> list[dict]:
    if not videos:
        return []
    vs = sorted(videos, key=lambda v: v["views"], reverse=True)
    best = vs[:max(3, int(len(vs) * top_share))]
    score, count = Counter(), Counter()
    for v in best:
        for w in set(keywords(v["title"])):
            score[w] += v["views"]; count[w] += 1
    ranked = [w for w, _ in score.most_common() if count[w] >= 2] or [w for w, _ in score.most_common()]
    return [{"keyword": w, "videos": count[w], "views": score[w],
             "examples": [v["title"] for v in best if w in keywords(v["title"])][:3]} for w in ranked[:n]]

def _handle(s: str) -> str:
    s = s.strip()
    m = re.search(r"youtube\.com/(@[\w.\-]+)", s)
    if m: return m.group(1)
    m = re.search(r"youtube\.com/channel/(UC[\w\-]+)", s)
    if m: return m.group(1)
    return s if s.startswith(("@", "UC")) else "@" + s

def fetch_api(handle: str, limit=500) -> dict:
    k = config.key("YOUTUBE_API_KEY"); y = "https://www.googleapis.com/youtube/v3"
    p = {"part": "snippet,statistics,contentDetails", "key": k}
    p.update({"id": handle} if handle.startswith("UC") else {"forHandle": handle})
    items = req("GET", f"{y}/channels", params=p).json().get("items") or []
    if not items:
        raise ProviderError(f"channel not found: {handle}")
    ch = items[0]; uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while len(ids) < limit:
        q = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50, "key": k}
        if tok: q["pageToken"] = tok
        j = req("GET", f"{y}/playlistItems", params=q).json()
        ids += [i["contentDetails"]["videoId"] for i in j.get("items", [])]
        tok = j.get("nextPageToken")
        if not tok: break
    videos = []
    for i in range(0, len(ids), 50):
        j = req("GET", f"{y}/videos", params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i+50]), "key": k}).json()
        for v in j.get("items", []):
            st = v.get("statistics", {})
            videos.append({"id": v["id"], "title": v["snippet"]["title"], "views": int(st.get("viewCount", 0)),
                           "likes": int(st.get("likeCount", 0)), "comments": int(st.get("commentCount", 0)),
                           "published": v["snippet"]["publishedAt"], "url": f"https://youtu.be/{v['id']}"})
    return {"channel": ch["snippet"]["title"], "subscribers": int(ch["statistics"].get("subscriberCount", 0)), "videos": videos, "via": "youtube_api"}

def fetch_ytdlp(handle: str, limit=500) -> dict:
    exe = shutil.which("yt-dlp")
    cmd = [exe] if exe else ["python", "-m", "yt_dlp"]
    base = f"https://www.youtube.com/{handle}" if handle.startswith("@") else f"https://www.youtube.com/channel/{handle}"
    videos, name = [], handle
    for tab in ("videos", "shorts"):
        try:
            out = subprocess.run(cmd + ["--flat-playlist", "-J", "--playlist-end", str(limit), f"{base}/{tab}"],
                                 capture_output=True, text=True, timeout=180)
            j = json.loads(out.stdout or "{}")
        except Exception:
            continue
        name = j.get("channel") or j.get("uploader") or name
        for e in j.get("entries") or []:
            if e.get("id"):
                videos.append({"id": e["id"], "title": e.get("title") or "", "views": int(e.get("view_count") or 0),
                               "type": tab, "url": f"https://youtu.be/{e['id']}"})
    if not videos:
        raise ProviderError("yt-dlp could not list the channel (install yt-dlp: pip install yt-dlp)")
    return {"channel": name, "subscribers": None, "videos": videos, "via": "yt-dlp"}

def scan(channel: str, limit=500) -> dict:
    h = _handle(channel)
    data = fetch_api(h, limit) if config.has("YOUTUBE_API_KEY") else fetch_ytdlp(h, limit)
    vids = data["videos"]
    data.update({
        "handle": h, "total_videos": len(vids), "total_views": sum(v["views"] for v in vids),
        "buckets": bucketize(vids), "top_topics": top_topics(vids),
        "top_videos": sorted(vids, key=lambda v: v["views"], reverse=True)[:10],
    })
    return data

def scan_instagram(username: str | None = None) -> dict:
    """Own IG account (username=None) or another Business/Creator account via business_discovery (likes only)."""
    tok, uid = config.key("IG_ACCESS_TOKEN"), config.key("IG_USER_ID")
    if not (tok and uid):
        raise ProviderError("IG_ACCESS_TOKEN / IG_USER_ID missing")
    g = "https://graph.facebook.com/v21.0"; f = "caption,like_count,comments_count,media_type,permalink,timestamp"
    if username:
        j = req("GET", f"{g}/{uid}", params={"access_token": tok, "fields": f"business_discovery.username({username}){{followers_count,media.limit(100){{{f}}}}}"}).json()
        media = j["business_discovery"]["media"]["data"]
    else:
        media = req("GET", f"{g}/{uid}/media", params={"access_token": tok, "fields": f, "limit": 100}).json().get("data", [])
    vids = [{"id": m["id"], "title": (m.get("caption") or "")[:100], "views": int(m.get("like_count", 0)), "url": m.get("permalink")} for m in media]
    return {"account": username or "me", "metric": "likes", "videos": vids, "buckets": bucketize(vids), "top_topics": top_topics(vids)}
