"""Trend finder: YouTube mostPopular + search (region IN), Google Trends (no key), Instagram hashtag search (optional)."""
from __future__ import annotations
import datetime as dt, re, xml.etree.ElementTree as ET
from collections import Counter
from . import config
from .http import req, ProviderError
from .textutil import keywords

YT = "https://www.googleapis.com/youtube/v3"

def youtube_trending(region="IN", max_results=50, category_id=None) -> list[dict]:
    k = config.key("YOUTUBE_API_KEY")
    if not k:
        raise ProviderError("YOUTUBE_API_KEY missing")
    p = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": max_results, "key": k}
    if category_id:
        p["videoCategoryId"] = category_id
    items = req("GET", f"{YT}/videos", params=p).json().get("items", [])
    return [{"source": "youtube", "title": i["snippet"]["title"], "id": i["id"],
             "views": int(i.get("statistics", {}).get("viewCount", 0)),
             "url": f"https://youtu.be/{i['id']}", "tags": i["snippet"].get("tags", [])[:10]} for i in items]

def youtube_search(query, region="IN", days=7, max_results=25) -> list[dict]:
    k = config.key("YOUTUBE_API_KEY")
    if not k:
        raise ProviderError("YOUTUBE_API_KEY missing")
    after = (dt.datetime.utcnow() - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    s = req("GET", f"{YT}/search", params={"part": "snippet", "q": query, "type": "video", "regionCode": region,
            "order": "viewCount", "publishedAfter": after, "maxResults": max_results, "key": k}).json()
    ids = [i["id"]["videoId"] for i in s.get("items", [])]
    if not ids:
        return []
    v = req("GET", f"{YT}/videos", params={"part": "snippet,statistics", "id": ",".join(ids), "key": k}).json()
    return [{"source": "youtube_search", "title": i["snippet"]["title"], "id": i["id"],
             "views": int(i.get("statistics", {}).get("viewCount", 0)), "url": f"https://youtu.be/{i['id']}"}
            for i in v.get("items", [])]

def _traffic(s: str) -> int:
    s = (s or "").replace(",", "").replace("+", "").strip().upper()
    m = re.match(r"([\d.]+)\s*([KM]?)", s)
    if not m:
        return 0
    n = float(m.group(1)); return int(n * {"K": 1e3, "M": 1e6}.get(m.group(2), 1))

def google_trends(region="IN") -> list[dict]:
    """Google Trends daily trending searches (public RSS, no key). Falls back to pytrends."""
    try:
        r = req("GET", "https://trends.google.com/trending/rss", params={"geo": region}, timeout=20)
        root = ET.fromstring(r.content)
        ns = {"ht": "https://trends.google.com/trending/rss"}
        out = []
        for it in root.iter("item"):
            news = [n.findtext("ht:news_item_title", default="", namespaces=ns) for n in it.findall("ht:news_item", ns)]
            out.append({"source": "google_trends", "title": it.findtext("title", ""),
                        "views": _traffic(it.findtext("ht:approx_traffic", "", ns)), "news": news[:2]})
        if out:
            return out
    except Exception:
        pass
    try:
        from pytrends.request import TrendReq
        df = TrendReq(hl="en-IN", tz=330).trending_searches(pn="india")
        return [{"source": "google_trends", "title": t, "views": 0} for t in df[0].tolist()]
    except Exception as e:
        raise ProviderError(f"google trends unavailable: {e}")

def google_related(niche: str, region="IN") -> list[dict]:
    """Rising related queries for your niche (pytrends)."""
    from pytrends.request import TrendReq
    py = TrendReq(hl="en-IN", tz=330)
    py.build_payload([niche[:90]], timeframe="now 7-d", geo=region)
    rq = py.related_queries().get(niche[:90], {}) or {}
    out = []
    for kind in ("rising", "top"):
        df = rq.get(kind)
        if df is not None:
            out += [{"source": f"google_{kind}", "title": r["query"], "views": 0, "interest": int(r["value"])} for _, r in df.head(15).iterrows()]
    return out

def instagram_hashtag(tag: str) -> list[dict]:
    tok, uid = config.key("IG_ACCESS_TOKEN"), config.key("IG_USER_ID")
    if not (tok and uid):
        raise ProviderError("IG_ACCESS_TOKEN / IG_USER_ID missing")
    g = "https://graph.facebook.com/v21.0"
    hid = req("GET", f"{g}/ig_hashtag_search", params={"user_id": uid, "q": tag.strip("#"), "access_token": tok}).json()["data"][0]["id"]
    media = req("GET", f"{g}/{hid}/top_media", params={"user_id": uid, "access_token": tok,
                "fields": "caption,like_count,comments_count,media_type,permalink"}).json().get("data", [])
    return [{"source": "instagram", "title": (m.get("caption") or "")[:120], "views": int(m.get("like_count", 0)) * 20,
             "likes": m.get("like_count", 0), "url": m.get("permalink")} for m in media]

MOCK = ["free AI tools 2026", "ChatGPT ke secret tricks", "YouTube Shorts viral kaise kare", "AI se paise kaise kamaye",
        "Gemini vs ChatGPT", "phone ki hidden settings", "AI video generator free", "Instagram reels growth hack"]

def find_topics(niche=None, region=None, limit=15, allow_mock=True) -> dict:
    """Merge every source that works; report which failed. Score = log-ish views + cross-source agreement."""
    s = config.settings(); niche = niche or s["niche"]; region = region or s["region"]
    items, errors = [], {}
    jobs = [("youtube_trending", lambda: youtube_trending(region)),
            ("youtube_search", lambda: youtube_search(niche.split(",")[0], region)),
            ("google_trends", lambda: google_trends(region)),
            ("google_related", lambda: google_related(niche.split(",")[0].strip(), region)),
            ("instagram", lambda: instagram_hashtag(niche.split(",")[0].replace(" ", "")))]
    for name, fn in jobs:
        try:
            items += fn()
        except Exception as e:
            errors[name] = str(e)[:200]
    mock = False
    if not items and allow_mock:
        mock = True
        items = [{"source": "mock", "title": t, "views": 1000 * (len(MOCK) - i)} for i, t in enumerate(MOCK)]
    kw = Counter()
    for it in items:
        for w in keywords(it["title"]):
            kw[w] += 1
    niche_words = set(keywords(niche))
    for it in items:
        ws = keywords(it["title"])
        agree = sum(kw[w] for w in ws) / (len(ws) or 1)
        boost = 2.0 if niche_words & set(ws) else 1.0
        it["score"] = round((len(str(max(it.get("views", 0), 1))) + agree) * boost, 2)
    items.sort(key=lambda x: x["score"], reverse=True)
    seen, top = set(), []
    for it in items:
        key = it["title"].lower()[:60]
        if key not in seen:
            seen.add(key); top.append(it)
    return {"topics": top[:limit], "hot_keywords": [w for w, _ in kw.most_common(20)], "errors": errors, "mock": mock}
