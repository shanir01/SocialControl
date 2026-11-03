"""Editor: 9:16 (1080x1920) short from clips/images + voiceover + captions + background music with ducking."""
from __future__ import annotations
import os, pathlib, shutil, tempfile
from .ff import ffmpeg, probe
from .captions import build_ass

W, H, FPS = 1080, 1920, 30
COVER = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"

def normalize(seg: dict, dur: float, out: str, idx: int = 0):
    """Any clip/image -> exactly dur seconds of 1080x1920@30 silent H.264."""
    if seg["type"] == "video":
        ffmpeg(["-stream_loop", "-1", "-i", seg["path"], "-t", f"{dur:.3f}", "-an",
                "-vf", f"{COVER},fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", out])
    else:  # image -> Ken Burns (slow zoom, alternating direction)
        frames = max(1, int(dur * FPS))
        z = "min(zoom+0.0009,1.12)" if idx % 2 == 0 else "if(eq(on,0),1.12,max(zoom-0.0009,1.0))"
        ffmpeg(["-loop", "1", "-i", seg["path"], "-t", f"{dur:.3f}",
                "-vf", f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                       f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", out])
    return out

def assemble(segments: list[dict], voice: str, words: list[dict], out: str, music: str | None = None,
             end_card: str | None = "- N I S H U", tail: float = 2.2, font: str = "Arial Black", music_volume: float = 0.22) -> dict:
    """segments: [{path, type: 'video'|'image', start?, end?}] in script order. Each segment covers its line's time;
    missing timings are spread evenly. Returns probe info of the result."""
    work = pathlib.Path(tempfile.mkdtemp(prefix="sc_edit_"))
    vdur = probe(voice)["duration"]; total = vdur + (tail if end_card else 0.4)
    # time per segment: follow script lines when given, else equal split
    n = len(segments)
    bounds = []
    for i, s in enumerate(segments):
        st = s.get("start", total * i / n); en = segments[i + 1].get("start", total * (i + 1) / n) if i + 1 < n else total
        bounds.append(max(0.5, en - st))
    drift = total - sum(bounds); bounds[-1] = max(0.5, bounds[-1] + drift)
    parts = []
    for i, (s, d) in enumerate(zip(segments, bounds)):
        parts.append(normalize(s, d, str(work / f"s{i:02d}.mp4"), i))
    with open(work / "list.txt", "w") as f:
        for p in parts: f.write(f"file '{p}'\n")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4"], cwd=work)
    (work / "caps.ass").write_text(build_ass(words, end_card, total, font=font), encoding="utf-8")
    shutil.copy(voice, work / ("voice" + pathlib.Path(voice).suffix))
    vname = "voice" + pathlib.Path(voice).suffix
    args = ["-i", "video.mp4", "-i", vname]
    if music:
        shutil.copy(music, work / ("music" + pathlib.Path(music).suffix)); args += ["-stream_loop", "-1", "-i", "music" + pathlib.Path(music).suffix]
        fc = (f"[0:v]ass=caps.ass[v];"
              f"[1:a]aresample=44100,aformat=channel_layouts=stereo,apad=whole_dur={total:.3f},asplit=2[vo][sc];"
              f"[2:a]aresample=44100,aformat=channel_layouts=stereo,volume={music_volume},atrim=0:{total:.3f}[mu];"
              f"[mu][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck];"
              f"[vo][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
    else:
        fc = f"[0:v]ass=caps.ass[v];[1:a]aresample=44100,aformat=channel_layouts=stereo,apad=whole_dur={total:.3f}[a]"
    ffmpeg(args + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(FPS),
                   "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.abspath(out)], cwd=work)
    shutil.rmtree(work, ignore_errors=True)
    info = probe(out); info["path"] = out
    return info

def segments_from_words(visuals: list[dict], words: list[dict]) -> list[dict]:
    """Attach each line's start time (from caption words) to its visual so cuts land on the spoken line."""
    starts = {}
    for w in words:
        starts.setdefault(w["line"], w["start"])
    out = []
    for i, v in enumerate(visuals):
        v = dict(v)
        if i in starts: v["start"] = 0.0 if i == 0 else starts[i]
        out.append(v)
    return out
