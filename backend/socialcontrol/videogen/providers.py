"""AI video providers. Each: name, available(), generate(prompt, style, seconds, out) -> path.
Raise ProviderError(quota=True) on limits so the orchestrator switches provider and cools it down."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, time
from .. import config
from ..http import req, download, ProviderError

STYLE = {"photo": "photorealistic cinematic", "cartoon": "2D cartoon animation, bold colors", "3d": "3D animated Pixar-style",
         "stock": "photorealistic"}

def styled(prompt, style): return f"{prompt}. {STYLE.get(style, style)}, vertical 9:16, smooth motion, no text, no logos"

def _poll(fn, every=6, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = fn()
        if r is not None: return r
        time.sleep(every)
    raise ProviderError("timed out waiting for video")

class Provider:
    name = "base"; keys: tuple = ()
    def available(self): return all(config.has(k) for k in self.keys)
    def generate(self, prompt, style, seconds, out): raise NotImplementedError

class Veo(Provider):
    """Google Veo through the Gemini API (AI Studio key; Veo needs a paid tier on most accounts)."""
    name, keys = "veo", ("GEMINI_API_KEY",)
    model = os.environ.get("VEO_MODEL", "veo-3.0-fast-generate-001")
    def generate(self, prompt, style, seconds, out):
        k = config.key("GEMINI_API_KEY"); base = "https://generativelanguage.googleapis.com/v1beta"
        op = req("POST", f"{base}/models/{self.model}:predictLongRunning", headers={"x-goog-api-key": k},
                 json={"instances": [{"prompt": styled(prompt, style)}], "parameters": {"aspectRatio": "9:16"}}).json()
        name = op["name"]
        def check():
            j = req("GET", f"{base}/{name}", headers={"x-goog-api-key": k}).json()
            if j.get("error"): raise ProviderError(f"veo: {j['error']}", quota="quota" in str(j['error']).lower())
            return j if j.get("done") else None
        j = _poll(check, 8, 900)
        uri = j["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
        return download(uri, out, headers={"x-goog-api-key": k})

class Fal(Provider):
    """fal.ai queue API — one key, many models (Kling, Luma, Minimax, Wan...). Model via FAL_VIDEO_MODEL."""
    name, keys = "fal", ("FAL_KEY",)
    model = os.environ.get("FAL_VIDEO_MODEL", "fal-ai/kling-video/v2.1/standard/text-to-video")
    def generate(self, prompt, style, seconds, out):
        h = {"Authorization": f"Key {config.key('FAL_KEY')}"}
        j = req("POST", f"https://queue.fal.run/{self.model}", headers=h,
                json={"prompt": styled(prompt, style), "duration": "5" if seconds <= 5 else "10", "aspect_ratio": "9:16"}).json()
        status_url, resp_url = j["status_url"], j["response_url"]
        def check():
            s = req("GET", status_url, headers=h).json()
            if s.get("status") == "COMPLETED": return True
            if s.get("status") in ("FAILED", "ERROR"): raise ProviderError(f"fal: {s}")
            return None
        _poll(check, 5, 900)
        r = req("GET", resp_url, headers=h).json()
        return download(r["video"]["url"], out)

class Kling(Provider):
    """Kling official API (JWT from access+secret key)."""
    name, keys = "kling", ("KLING_ACCESS_KEY", "KLING_SECRET_KEY")
    base = os.environ.get("KLING_API_BASE", "https://api-singapore.klingai.com")
    def _jwt(self):
        b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=")
        now = int(time.time())
        msg = b64({"alg": "HS256", "typ": "JWT"}) + b"." + b64({"iss": config.key("KLING_ACCESS_KEY"), "exp": now + 1800, "nbf": now - 5})
        sig = base64.urlsafe_b64encode(hmac.new(config.key("KLING_SECRET_KEY").encode(), msg, hashlib.sha256).digest()).rstrip(b"=")
        return (msg + b"." + sig).decode()
    def generate(self, prompt, style, seconds, out):
        h = {"Authorization": f"Bearer {self._jwt()}"}
        j = req("POST", f"{self.base}/v1/videos/text2video", headers=h,
                json={"model_name": "kling-v1-6", "prompt": styled(prompt, style), "aspect_ratio": "9:16", "duration": "5" if seconds <= 5 else "10"}).json()
        if j.get("code") not in (0, None): raise ProviderError(f"kling: {j}", quota=j.get("code") in (1102, 1103, 1104))
        tid = j["data"]["task_id"]
        def check():
            d = req("GET", f"{self.base}/v1/videos/text2video/{tid}", headers={"Authorization": f"Bearer {self._jwt()}"}).json()["data"]
            if d["task_status"] == "succeed": return d["task_result"]["videos"][0]["url"]
            if d["task_status"] == "failed": raise ProviderError(f"kling failed: {d.get('task_status_msg')}")
            return None
        return download(_poll(check, 8, 900), out)

class Runway(Provider):
    """Runway API: image -> video (gen4_turbo). Needs a first frame; we make one with Gemini or stock photo."""
    name, keys = "runway", ("RUNWAY_API_KEY",)
    def generate(self, prompt, style, seconds, out, image_path=None):
        if not image_path: raise ProviderError("runway needs a start image (pass image_path)")
        h = {"Authorization": f"Bearer {config.key('RUNWAY_API_KEY')}", "X-Runway-Version": "2024-11-06"}
        data_uri = "data:image/png;base64," + base64.b64encode(open(image_path, "rb").read()).decode()
        j = req("POST", "https://api.dev.runwayml.com/v1/image_to_video", headers=h,
                json={"model": "gen4_turbo", "promptImage": data_uri, "promptText": styled(prompt, style)[:900],
                      "ratio": "720:1280", "duration": 5 if seconds <= 5 else 10}).json()
        tid = j["id"]
        def check():
            t = req("GET", f"https://api.dev.runwayml.com/v1/tasks/{tid}", headers=h).json()
            if t["status"] == "SUCCEEDED": return t["output"][0]
            if t["status"] in ("FAILED", "CANCELLED"): raise ProviderError(f"runway: {t.get('failure')}", quota="credit" in str(t).lower())
            return None
        return download(_poll(check, 6, 900), out)

class Luma(Provider):
    name, keys = "luma", ("LUMA_API_KEY",)
    def generate(self, prompt, style, seconds, out):
        h = {"Authorization": f"Bearer {config.key('LUMA_API_KEY')}"}
        j = req("POST", "https://api.lumalabs.ai/dream-machine/v1/generations", headers=h,
                json={"prompt": styled(prompt, style), "model": "ray-2", "aspect_ratio": "9:16", "resolution": "720p", "duration": "5s"}).json()
        gid = j["id"]
        def check():
            g = req("GET", f"https://api.lumalabs.ai/dream-machine/v1/generations/{gid}", headers=h).json()
            if g["state"] == "completed": return g["assets"]["video"]
            if g["state"] == "failed": raise ProviderError(f"luma: {g.get('failure_reason')}")
            return None
        return download(_poll(check, 6, 900), out)

class Stock(Provider):
    """Always-safe fallback: free-license stock clip (Pexels/Pixabay)."""
    name = "stock"
    def available(self): return config.has("PEXELS_API_KEY") or config.has("PIXABAY_API_KEY")
    def generate(self, prompt, style, seconds, out, query=None):
        from .. import media
        q = query or " ".join(prompt.split()[:4])
        try: return media.pexels_video(q, out)["path"]
        except ProviderError: return media.pixabay_video(q, out)["path"]

ALL = [Veo(), Kling(), Runway(), Luma(), Fal(), Stock()]
