"""Optional lip-sync: make the character's mouth follow the Hindi voice line.
Uses fal.ai (FAL_KEY from Settings). Model via FAL_LIPSYNC_MODEL (default sync-labs lipsync).
No key -> skipped (the shot keeps its natural motion; captions + voice still work)."""
from __future__ import annotations
import base64, os
from . import config
from .http import req, download, ProviderError

MODEL = os.environ.get("FAL_LIPSYNC_MODEL", "fal-ai/sync-lipsync")
MAX_INLINE = 9 * 1024 * 1024  # data-URI upload limit we allow per file

def available() -> bool:
    return config.has("FAL_KEY")

def _data_uri(path, mime):
    b = open(path, "rb").read()
    if len(b) > MAX_INLINE: raise ProviderError(f"lipsync: {os.path.basename(path)} too big for inline upload ({len(b)//1024} KB)")
    return f"data:{mime};base64," + base64.b64encode(b).decode()

def apply(video: str, audio: str, out: str) -> str:
    """video (shot clip) + audio (that shot's voice line) -> lip-synced clip."""
    if not available(): raise ProviderError("lipsync: FAL_KEY missing")
    from .videogen.providers import _poll
    h = {"Authorization": f"Key {config.key('FAL_KEY')}"}
    j = req("POST", f"https://queue.fal.run/{MODEL}", headers=h,
            json={"video_url": _data_uri(video, "video/mp4"), "audio_url": _data_uri(audio, "audio/mpeg"), "sync_mode": "cut_off"}).json()
    status_url, resp_url = j["status_url"], j["response_url"]
    def check():
        s = req("GET", status_url, headers=h).json()
        if s.get("status") == "COMPLETED": return True
        if s.get("status") in ("FAILED", "ERROR"): raise ProviderError(f"lipsync: {s}")
        return None
    _poll(check, 5, 900)
    r = req("GET", resp_url, headers=h).json()
    return download(r["video"]["url"], out)
