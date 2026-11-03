"""Voice: Edge TTS (free, Hindi neural voices, gives word timings) or ElevenLabs (optional, paid)."""
from __future__ import annotations
import asyncio, os, re, tempfile
from . import config
from .http import req, ProviderError
from .ff import ffmpeg, probe

HINDI_VOICES = {"hi-IN-SwaraNeural": "Swara (female)", "hi-IN-MadhurNeural": "Madhur (male)"}

def edge_tts(text: str, out_mp3: str, voice="hi-IN-SwaraNeural", rate="+8%") -> list[dict]:
    """Returns word timings [{word, start, end}] in seconds, read from the voice itself."""
    import edge_tts as et
    async def go():
        c = et.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        words = []
        with open(out_mp3, "wb") as f:
            async for ch in c.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 1e7
                    words.append({"word": ch["text"], "start": s, "end": s + ch["duration"] / 1e7})
        return words
    return asyncio.run(go())

def elevenlabs(text: str, out_mp3: str) -> list[dict]:
    k, vid = config.key("ELEVENLABS_API_KEY"), config.key("ELEVENLABS_VOICE_ID") or "21m00Tcm4TlvDq8ikWAM"
    if not k: raise ProviderError("ELEVENLABS_API_KEY missing")
    import base64
    j = req("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps", headers={"xi-api-key": k},
            json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=180).json()
    open(out_mp3, "wb").write(base64.b64decode(j["audio_base64"]))
    al = j.get("alignment") or {}
    ends = al.get("character_end_times_seconds") or [0]
    st = al.get("character_start_times_seconds") or [0]
    return [{"word": text, "start": st[0], "end": ends[-1]}]

def speak_lines(lines: list[dict], out_audio: str, engine="edge", voice="hi-IN-SwaraNeural", gap=0.18) -> list[dict]:
    """Each line is spoken separately (exact line timing), then joined into one track.
    The voice reads Devanagari (natural Hindi accent); captions show Roman Hinglish words.
    Returns caption words [{word,start,end,line,highlight}]."""
    tmp = tempfile.mkdtemp(prefix="sc_voice_")
    parts, words, t = [], [], 0.0
    for i, l in enumerate(lines):
        text = (l.get("devanagari") or l["roman"]).strip()
        p = os.path.join(tmp, f"l{i}.mp3")
        if engine == "elevenlabs" and config.has("ELEVENLABS_API_KEY"):
            timed = elevenlabs(text, p)
        else:
            timed = edge_tts(text, p, voice)
        dur = probe(p)["duration"]
        if timed:  # trim the TTS's own leading/trailing silence so the short keeps a fast pace
            s, e = timed[0]["start"], min(timed[-1]["end"], dur)
            a, b = max(0.0, s - 0.06), min(dur, e + 0.15)
            tp = os.path.join(tmp, f"l{i}t.mp3")
            ffmpeg(["-i", p, "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-c:a", "libmp3lame", "-b:a", "96k", tp])
            p, dur, s, e = tp, probe(tp)["duration"], s - a, e - a
        else:
            s, e = 0.05, dur
        words += line_words(l, i, t + s, t + e)
        parts.append(p); t += dur + gap
    # join with small gaps
    lst = os.path.join(tmp, "list.txt"); sil = os.path.join(tmp, "gap.mp3")
    ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono", "-t", str(gap), "-c:a", "libmp3lame", "-b:a", "48k", sil])
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\nfile '{sil}'\n")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", out_audio])
    return words

def line_words(l: dict, li: int, start: float, end: float) -> list[dict]:
    roman = l["roman"].split()
    kws = {k.lower().strip(".,!?") for k in l.get("keywords", []) for k in k.split()}
    weights = [max(len(w), 2) + 1 for w in roman]; tot = sum(weights) or 1; t = start; out = []
    for w, wt in zip(roman, weights):
        d = (end - start) * wt / tot
        clean = w.lower().strip(".,!?:;\"'")
        out.append({"word": w, "start": round(t, 3), "end": round(t + d, 3), "line": li, "highlight": clean in kws})
        t += d
    return out
