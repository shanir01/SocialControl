"""Views tracker: every post is recorded; refresh pulls current views per video per platform."""
from __future__ import annotations
import datetime as dt, json
from . import config
from .http import req

DB = config.DATA / "posts.json"

def _load(): return json.loads(DB.read_text("utf-8")) if DB.exists() else []
def _save(rows): DB.write_text(json.dumps(rows, indent=2, ensure_ascii=False), "utf-8")

def record(post: dict, title: str, run_id: str = ""):
    rows = _load()
    rows.append({**post, "title": title, "run": run_id, "posted_at": dt.datetime.now().isoformat(timespec="seconds"), "views": 0})
    _save(rows)

def refresh() -> dict:
    rows = _load()
    yt_ids = [r["id"] for r in rows if r["platform"] == "youtube"]
    if yt_ids and config.has("YOUTUBE_API_KEY"):
        for i in range(0, len(yt_ids), 50):
            j = req("GET", "https://www.googleapis.com/youtube/v3/videos", params={"part": "statistics", "id": ",".join(yt_ids[i:i+50]), "key": config.key("YOUTUBE_API_KEY")}).json()
            st = {v["id"]: v["statistics"] for v in j.get("items", [])}
            for r in rows:
                if r["id"] in st:
                    r["views"] = int(st[r["id"]].get("viewCount", 0)); r["likes"] = int(st[r["id"]].get("likeCount", 0))
    tok = config.key("IG_ACCESS_TOKEN")
    for r in rows:
        if r["platform"] == "instagram" and tok:
            try:
                j = req("GET", f"https://graph.facebook.com/v21.0/{r['id']}/insights", params={"metric": "views,likes", "access_token": tok}).json()
                for m in j.get("data", []):
                    r[m["name"]] = m["values"][0]["value"]
            except Exception as e:
                r["error"] = str(e)[:120]
    _save(rows)
    return report(rows)

def report(rows=None) -> dict:
    rows = rows if rows is not None else _load()
    per = {}
    for r in rows:
        p = per.setdefault(r["platform"], {"videos": 0, "views": 0}); p["videos"] += 1; p["views"] += int(r.get("views") or 0)
    return {"total_views": sum(p["views"] for p in per.values()), "per_platform": per,
            "videos": sorted(rows, key=lambda r: -int(r.get("views") or 0))}
