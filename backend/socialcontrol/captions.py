"""Roman-Hinglish word-by-word captions (ASS) — NISHU house style: white bold text, black outline,
spoken word pops (bigger), keywords in YELLOW. Rendered by ffmpeg/libass."""
from __future__ import annotations

def ts(t: float) -> str:
    t = max(0.0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def chunks(words: list[dict], max_words=3, max_chars=18) -> list[list[dict]]:
    """Group words into short on-screen phrases; never across script lines."""
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or cur[-1]["line"] != w["line"]
                    or sum(len(x["word"]) + 1 for x in cur) + len(w["word"]) > max_chars):
            out.append(cur); cur = []
        cur.append(w)
    if cur: out.append(cur)
    return out

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,{marginv},1
Style: End,{font},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,6,0,1,6,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def build_ass(words: list[dict], end_card: str | None = None, total: float | None = None, font="Arial Black",
              size=104, marginv=600, highlight="&H0000FFFF&") -> str:
    lines = [HEADER.format(font=font, size=size, marginv=marginv)]
    for ch in chunks(words):
        for i, w in enumerate(ch):
            start = w["start"]; end = ch[i + 1]["start"] if i + 1 < len(ch) else w["end"]
            parts = []
            for j, x in enumerate(ch):
                txt = x["word"].upper().replace("{", "(").replace("}", ")")
                col = f"\\c{highlight}" if x.get("highlight") else "\\c&H00FFFFFF&"
                pop = "\\fscx118\\fscy118" if j == i else "\\fscx100\\fscy100"
                parts.append("{" + col + pop + "}" + txt)
            lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{{\\blur0.6}}" + " ".join(parts))
    if end_card and total:
        lines.append(f"Dialogue: 1,{ts(total - 2.2)},{ts(total)},End,,0,0,0,,{{\\fad(300,0)}}{end_card}")
    return "\n".join(lines) + "\n"
