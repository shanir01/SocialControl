"""Score generated clips with simple, explainable heuristics (+ optional Gemini vision rating)."""
from __future__ import annotations
import os, re, subprocess, tempfile
from ..ff import _bin, probe

def black_ratio(path: str, duration: float) -> float:
    """Share of the clip that is (near) black, via ffmpeg blackdetect."""
    try:
        r = subprocess.run([_bin("ffmpeg"), "-hide_banner", "-i", path, "-vf", "blackdetect=d=0.1:pix_th=0.10", "-an", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=300)
        tot = sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", r.stderr))
        return min(1.0, tot / duration) if duration else 1.0
    except Exception:
        return 0.0

def metrics(path: str) -> dict:
    p = probe(path)
    p["black_ratio"] = black_ratio(path, p["duration"])
    p["size_mb"] = os.path.getsize(path) / 1e6 if os.path.exists(path) else 0
    return p

def score_metrics(m: dict, min_duration: float = 3.0, want_portrait: bool = True, vision: float | None = None) -> dict:
    """Pure function (unit-tested). 0-100. Returns {score, reasons}."""
    reasons, s = [], 0.0
    d = m.get("duration", 0)
    if d <= 0 or m.get("width", 0) == 0:
        return {"score": 0.0, "reasons": ["unreadable / empty file"]}
    s += 30 if d >= min_duration else 30 * d / min_duration
    if d < min_duration: reasons.append(f"short ({d:.1f}s)")
    short_side = min(m["width"], m["height"])
    s += min(25.0, 25.0 * short_side / 1080)
    if short_side < 720: reasons.append(f"low res {m['width']}x{m['height']}")
    portrait = m["height"] > m["width"]
    if portrait == want_portrait: s += 15
    else: s += 5; reasons.append("wrong orientation (will be cropped)")
    br = m.get("black_ratio", 0)
    s += 20 * (1 - min(1.0, br * 3))
    if br > 0.05: reasons.append(f"black frames {br:.0%}")
    if vision is not None:
        s += vision  # 0-10
        reasons.append(f"vision {vision:.1f}/10")
    else:
        s += 5  # neutral when no vision rating
    return {"score": round(s, 1), "reasons": reasons or ["ok"]}

def sample_frames(path: str, n=3) -> list[str]:
    d = probe(path)["duration"] or 1; out = []
    tmp = tempfile.mkdtemp(prefix="sc_frames_")
    for i in range(n):
        f = os.path.join(tmp, f"f{i}.jpg")
        subprocess.run([_bin("ffmpeg"), "-y", "-loglevel", "error", "-ss", f"{d*(i+0.5)/n:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=480:-2", f],
                       capture_output=True, timeout=60)
        if os.path.exists(f): out.append(f)
    return out

def score_file(path: str, prompt: str = "", use_vision: bool = False, min_duration: float = 3.0) -> dict:
    m = metrics(path); vision = None
    if use_vision:
        try:
            from .. import ai
            vision = ai.rate_frames(sample_frames(path), prompt)
        except Exception:
            vision = None
    r = score_metrics(m, min_duration=min_duration, vision=vision); r["metrics"] = m
    return r
