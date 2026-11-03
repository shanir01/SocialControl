from __future__ import annotations
import time, requests

UA = {"User-Agent": "SocialControl/1.0 (+https://github.com/shanir01/SocialControl)"}

class ProviderError(Exception):
    """quota=True means: try next provider (rate limit / credits / 402 / 429)."""
    def __init__(self, msg, quota=False):
        super().__init__(msg); self.quota = quota

def req(method, url, retries=2, **kw):
    kw.setdefault("timeout", 60)
    h = dict(UA); h.update(kw.pop("headers", {}) or {})
    last = None
    for i in range(retries + 1):
        try:
            r = requests.request(method, url, headers=h, **kw)
        except requests.RequestException as e:
            last = ProviderError(f"network: {e}"); time.sleep(1.5 * (i + 1)); continue
        if r.status_code in (402, 429) or (r.status_code == 403 and "quota" in r.text.lower()):
            raise ProviderError(f"{r.status_code} quota/limit: {r.text[:300]}", quota=True)
        if r.status_code >= 500 and i < retries:
            time.sleep(1.5 * (i + 1)); continue
        if r.status_code >= 400:
            raise ProviderError(f"{r.status_code}: {r.text[:400]}")
        return r
    raise last or ProviderError("request failed")

def download(url, path, **kw):
    r = req("GET", url, stream=True, timeout=180, **kw)
    with open(path, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    return path
