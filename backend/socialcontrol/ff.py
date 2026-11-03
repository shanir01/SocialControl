"""ffmpeg helpers. Uses system ffmpeg, else FFMPEG env, else imageio-ffmpeg's bundled binary."""
from __future__ import annotations
import json, os, shutil, subprocess

def _bin(name):
    env = os.environ.get(name.upper())
    if env: return env
    p = shutil.which(name)
    if p: return p
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    raise RuntimeError(f"{name} not found. Windows: 'winget install Gyan.FFmpeg'  |  Linux: 'sudo apt install ffmpeg'")

def ffmpeg(args, cwd=None, timeout=900):
    cmd = [_bin("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error"] + [str(a) for a in args]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-800:]}")
    return r

def probe(path) -> dict:
    try:
        exe = _bin("ffprobe")
        r = subprocess.run([exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                           capture_output=True, text=True, timeout=60)
        j = json.loads(r.stdout or "{}")
    except RuntimeError:  # no ffprobe (imageio-ffmpeg only ships ffmpeg): parse ffmpeg -i
        import re
        r = subprocess.run([_bin("ffmpeg"), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr); d = int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)) if m else 0
        m2 = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", r.stderr)
        return {"duration": d, "width": int(m2.group(1)) if m2 else 0, "height": int(m2.group(2)) if m2 else 0, "has_audio": "Audio:" in r.stderr}
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    return {"duration": float(j.get("format", {}).get("duration", 0) or 0), "width": int(v.get("width", 0) or 0),
            "height": int(v.get("height", 0) or 0), "has_audio": a is not None}
