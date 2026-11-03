"""Copyright-safe media only: Pexels, Pixabay (free licenses), AI images (Gemini), and your own local files.
No scraping of other people's content (Pinterest etc.)."""
from __future__ import annotations
import pathlib, random
from . import config
from .http import req, download, ProviderError

def pexels_video(query: str, out: str) -> dict:
    k = config.key("PEXELS_API_KEY")
    if not k: raise ProviderError("PEXELS_API_KEY missing")
    j = req("GET", "https://api.pexels.com/videos/search", headers={"Authorization": k},
            params={"query": query, "orientation": "portrait", "per_page": 10, "size": "medium"}).json()
    vids = j.get("videos") or []
    if not vids: raise ProviderError(f"pexels: nothing for {query}")
    v = random.choice(vids[:5])
    files = sorted([f for f in v["video_files"] if f.get("height")], key=lambda f: abs(f["height"] - 1920))
    download(files[0]["link"], out)
    return {"path": out, "type": "video", "source": "pexels", "credit": v.get("user", {}).get("name"), "page": v.get("url")}

def pixabay_video(query: str, out: str) -> dict:
    k = config.key("PIXABAY_API_KEY")
    if not k: raise ProviderError("PIXABAY_API_KEY missing")
    j = req("GET", "https://pixabay.com/api/videos/", params={"key": k, "q": query[:100], "per_page": 10, "safesearch": "true"}).json()
    hits = j.get("hits") or []
    if not hits: raise ProviderError(f"pixabay: nothing for {query}")
    h = random.choice(hits[:5]); vv = h["videos"]
    url = (vv.get("large") or {}).get("url") or (vv.get("medium") or {}).get("url")
    download(url, out)
    return {"path": out, "type": "video", "source": "pixabay", "credit": h.get("user"), "page": h.get("pageURL")}

def pexels_photo(query: str, out: str) -> dict:
    k = config.key("PEXELS_API_KEY")
    if not k: raise ProviderError("PEXELS_API_KEY missing")
    j = req("GET", "https://api.pexels.com/v1/search", headers={"Authorization": k},
            params={"query": query, "orientation": "portrait", "per_page": 10}).json()
    ph = j.get("photos") or []
    if not ph: raise ProviderError("pexels photo: none")
    p = random.choice(ph[:5]); download(p["src"]["portrait"], out)
    return {"path": out, "type": "image", "source": "pexels", "credit": p.get("photographer"), "page": p.get("url")}

def pixabay_photo(query: str, out: str) -> dict:
    k = config.key("PIXABAY_API_KEY")
    if not k: raise ProviderError("PIXABAY_API_KEY missing")
    j = req("GET", "https://pixabay.com/api/", params={"key": k, "q": query[:100], "orientation": "vertical", "per_page": 10, "safesearch": "true"}).json()
    hits = j.get("hits") or []
    if not hits: raise ProviderError("pixabay photo: none")
    h = random.choice(hits[:5]); download(h["largeImageURL"], out)
    return {"path": out, "type": "image", "source": "pixabay", "credit": h.get("user"), "page": h.get("pageURL")}

def ai_image(prompt: str, out: str, style="photo") -> dict:
    from . import ai
    ai.image(prompt, out, style)
    return {"path": out, "type": "image", "source": "gemini-ai", "credit": "AI generated"}

def get_visual(line: dict, out_base: str, style="photo", prefer_video=True) -> dict:
    """Try sources in order; return first that works. errors are kept for the run log."""
    q = line.get("broll") or line.get("roman", "")[:40]
    order = []
    if style in ("cartoon", "3d"):
        order = [("ai_image", lambda: ai_image(line.get("image_prompt", q), out_base + ".png", style))]
    if prefer_video:
        order += [("pexels_video", lambda: pexels_video(q, out_base + ".mp4")), ("pixabay_video", lambda: pixabay_video(q, out_base + ".mp4"))]
    order += [("pexels_photo", lambda: pexels_photo(q, out_base + ".jpg")), ("pixabay_photo", lambda: pixabay_photo(q, out_base + ".jpg")),
              ("ai_image", lambda: ai_image(line.get("image_prompt", q), out_base + ".png", style))]
    errors = {}
    for name, fn in order:
        try:
            r = fn(); r["errors"] = errors; return r
        except Exception as e:
            errors[name] = str(e)[:160]
    raise ProviderError(f"no visual for '{q}': {errors}")

def local_music() -> str | None:
    """Royalty-free tracks you downloaded yourself (Pixabay Music / YouTube Audio Library) go in assets/music/."""
    d = config.ROOT / "assets" / "music"
    files = [p for p in d.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")] if d.exists() else []
    return str(random.choice(files)) if files else None
