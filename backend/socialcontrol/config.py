"""Keys & settings. Keys come from (1) environment / .env  (2) data/settings.json written by the Settings screen.
Keys are never written into the repo: data/ and .env are git-ignored."""
from __future__ import annotations
import json, os, pathlib, threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = pathlib.Path(os.environ.get("SC_DATA_DIR", ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA / "settings.json"
_lock = threading.Lock()

try:  # optional
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

# Every key the app knows, with where to get it. One place only (Settings screen reads this list).
KEYS = [
    # group, env name, label, where to get it, needed for
    ("Trends", "YOUTUBE_API_KEY", "YouTube Data API v3 key", "https://console.cloud.google.com/apis/library/youtube.googleapis.com", "Trending videos + channel scan"),
    ("Trends", "IG_ACCESS_TOKEN", "Instagram Graph API token (Business/Creator)", "https://developers.facebook.com/tools/explorer/", "IG hashtag trends + Reels post"),
    ("Trends", "IG_USER_ID", "Instagram Business account ID", "https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/getting-started", "IG hashtag trends + Reels post"),
    ("AI", "GEMINI_API_KEY", "Gemini API key (Google AI Studio)", "https://aistudio.google.com/app/apikey", "Script, title, description, hashtags, AI images, Veo, quality rating"),
    ("Media", "PEXELS_API_KEY", "Pexels API key", "https://www.pexels.com/api/", "Free stock videos/photos"),
    ("Media", "PIXABAY_API_KEY", "Pixabay API key", "https://pixabay.com/api/docs/", "Free stock videos/photos"),
    ("Voice", "ELEVENLABS_API_KEY", "ElevenLabs API key (optional)", "https://elevenlabs.io/app/settings/api-keys", "Premium voice (Edge TTS is free default)"),
    ("Voice", "ELEVENLABS_VOICE_ID", "ElevenLabs voice ID (optional)", "https://elevenlabs.io/app/voice-library", "Premium voice"),
    ("AI Video", "FAL_KEY", "fal.ai key (optional)", "https://fal.ai/dashboard/keys", "AI video (Kling/Luma/Minimax via fal) + Aura reel lip-sync"),
    ("AI Video", "KLING_ACCESS_KEY", "Kling access key (optional)", "https://app.klingai.com/global/dev/api-key", "AI video"),
    ("AI Video", "KLING_SECRET_KEY", "Kling secret key (optional)", "https://app.klingai.com/global/dev/api-key", "AI video"),
    ("AI Video", "RUNWAY_API_KEY", "Runway API key (optional)", "https://dev.runwayml.com/", "AI video"),
    ("AI Video", "LUMA_API_KEY", "Luma Dream Machine key (optional)", "https://lumalabs.ai/dream-machine/api/keys", "AI video"),
    ("Post", "YT_CLIENT_SECRET_FILE", "YouTube OAuth client_secret.json path", "https://console.cloud.google.com/apis/credentials", "Auto upload + Full Control (API mode)"),
    ("Post", "PINTEREST_ACCESS_TOKEN", "Pinterest token (optional, apni video post)", "https://developers.pinterest.com/apps/", "Post your own video as a Pin"),
    ("Post", "PINTEREST_BOARD_ID", "Pinterest board ID (optional)", "https://developers.pinterest.com/docs/api/v5/boards-list/", "Post your own video as a Pin"),
]
KEY_NAMES = [k[1] for k in KEYS]

DEFAULT_SETTINGS = {
    "region": "IN",
    "language": "hi",
    "niche": "AI tools, tech tips",
    "channel_to_scan": "@javagoat9",
    "voice": "hi-IN-SwaraNeural",
    "voice_engine": "edge",          # edge | elevenlabs
    "video_style": "photo",          # photo | cartoon | 3d | stock
    "use_ai_video": True,
    "post_youtube": False,
    "post_instagram": False,
    "post_pinterest": False,
    "privacy": "private",            # first upload private, you check, then public
    "daily_time": "18:30",
    "scheduler_on": False,
    "end_card": "- N I S H U",
    "fc_update_metadata": False,     # Full Control: also improve old videos' title/description/tags (API)
    "fc_videos_per_session": 2,      # Full Control: videos to make from the topic list
    "aura_voice": "hi-IN-MadhurNeural",  # AI Animal Aura reel: deep male Hindi voice
    "aura_lipsync": True,            # AI Animal Aura reel: lip-sync talking shots when FAL_KEY is set
}

def _read() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text("utf-8"))
        except Exception:
            return {}
    return {}

def _env_override(k, default):
    v = os.environ.get("SC_SET_" + k.upper())
    if v is None: return None
    if isinstance(default, bool): return v.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int): return int(v)
    return v

def settings() -> dict:
    """Defaults < Settings screen (data/settings.json) < SC_SET_<NAME> env (used by GitHub Actions)."""
    s = dict(DEFAULT_SETTINGS); s.update({k: v for k, v in _read().items() if k not in KEY_NAMES and k in DEFAULT_SETTINGS})
    for k, d in DEFAULT_SETTINGS.items():
        o = _env_override(k, d)
        if o is not None: s[k] = o
    return s

def save_settings(update: dict) -> dict:
    with _lock:
        cur = _read(); cur.update(update)
        SETTINGS_FILE.write_text(json.dumps(cur, indent=2, ensure_ascii=False), "utf-8")
    return settings()

def key(name: str) -> str:
    """Env wins, then settings.json. Empty string when missing."""
    v = os.environ.get(name) or _read().get(name) or ""
    return str(v).strip()

def has(name: str) -> bool:
    return bool(key(name))

def keys_status() -> list[dict]:
    out = []
    for group, name, label, url, why in KEYS:
        v = key(name)
        out.append({"group": group, "name": name, "label": label, "url": url, "why": why,
                    "set": bool(v), "preview": (v[:3] + "…" + v[-2:]) if len(v) > 8 else ("set" if v else "")})
    return out
