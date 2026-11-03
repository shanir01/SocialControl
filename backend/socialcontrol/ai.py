"""Gemini (Google AI Studio key): script, title, description, hashtags, AI images, vision rating.
Without a key, offline templates keep the pipeline runnable (marked offline=True)."""
from __future__ import annotations
import base64, json, os, re
from . import config
from .http import req, ProviderError

API = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

def _gen(parts, model=TEXT_MODEL, json_mode=False, image=False):
    k = config.key("GEMINI_API_KEY")
    if not k:
        raise ProviderError("GEMINI_API_KEY missing")
    body = {"contents": [{"parts": parts}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    if image:
        body["generationConfig"] = {"responseModalities": ["IMAGE", "TEXT"]}
    return req("POST", f"{API}/models/{model}:generateContent", headers={"x-goog-api-key": k}, json=body, timeout=120).json()

def _text(j):
    try:
        return "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
    except Exception:
        raise ProviderError(f"gemini: empty answer {str(j)[:200]}")

SCRIPT_PROMPT = """You are a viral Indian short-video writer for the creator NISHU (YouTube @javagoat9, Instagram @shanir.ai).
Topic: {topic}
Write a {seconds}-second 9:16 short in natural Hinglish (Hindi + English, how young Indians talk). Strong hook in line 1,
fast value, CTA at the end ("Comment karo ... / follow karo"). Return ONLY JSON:
{{"title": "<=70 chars, curiosity + 1 emoji",
  "lines": [{{"roman": "Roman Hinglish line (captions)", "devanagari": "same line in Devanagari for the Hindi voice, English tech words may stay in English",
             "keywords": ["1-2 words from roman to highlight yellow"], "broll": "2-4 word English stock-footage search query",
             "image_prompt": "vivid English prompt for an AI image/video of this moment"}}],
  "description": "2-3 lines Hinglish + CTA",
  "hashtags": ["exactly 5 hashtags, most viral first, with #"],
  "tags": ["10 YouTube tags"]}}
6 to 10 lines. No copyrighted characters, no real brand logos."""

def write_script(topic: str, seconds: int = 45) -> dict:
    try:
        j = _gen([{"text": SCRIPT_PROMPT.format(topic=topic, seconds=seconds)}], json_mode=True)
        data = json.loads(re.sub(r"^```(json)?|```$", "", _text(j).strip()))
        data["offline"] = False
        return data
    except ProviderError:
        if config.has("GEMINI_API_KEY"):
            raise
        return offline_script(topic)

def offline_script(topic: str) -> dict:
    """Key-free template so the editor/voice can be tested. Replace with Gemini for real videos."""
    t = topic.strip()
    lines = [
        ("Ruko! {t} ke baare me ye baat 90% log nahi jaante", "रुको! {t} के बारे में ये बात नब्बे प्रतिशत लोग नहीं जानते", ["Ruko", "90%"], "surprised person phone"),
        ("Aaj main tumhe 3 aise tarike bataunga jo sach me kaam karte hain", "आज मैं तुम्हें तीन ऐसे तरीके बताऊंगा जो सच में काम करते हैं", ["3", "tarike"], "person explaining"),
        ("Pehla tarika: roz sirf 10 minute do, consistency hi asli game hai", "पहला तरीका: रोज़ सिर्फ दस मिनट दो, consistency ही असली game है", ["consistency", "game"], "clock time lapse"),
        ("Doosra: trending topic pakdo, wahi views laata hai", "दूसरा: trending topic पकड़ो, वही views लाता है", ["trending", "views"], "graph growth"),
        ("Teesra: AI tools se kaam 10 guna fast karo", "तीसरा: AI tools से काम दस गुना fast करो", ["AI", "fast"], "futuristic technology"),
        ("Video kaam ki lagi? Comment karo AI aur follow kar lo", "Video काम की लगी? Comment करो AI और follow कर लो", ["Comment", "follow"], "smartphone social media"),
    ]
    return {"title": f"{t[:50]} ka sach 😱", "offline": True,
            "lines": [{"roman": r.format(t=t), "devanagari": d.format(t=t), "keywords": k, "broll": b,
                       "image_prompt": f"cinematic vertical shot, {b}, vibrant colors"} for r, d, k, b in lines],
            "description": f"{t} — 3 kaam ke tarike 🔥\nComment karo AI 👇 Follow for more!",
            "hashtags": ["#viral", "#aitools", "#trending", "#shorts", "#reels"],
            "tags": [t, "viral", "ai tools", "hindi", "shorts", "tips", "tech", "india", "trending", "javagoat9"]}

def video_metadata(title: str, description: str = "", views: int = 0, niche: str = "") -> dict:
    """Used by Full Control: better title/description/tags for an existing video."""
    p = (f"Improve this YouTube video's metadata for search + CTR, Hinglish, honest (no clickbait lies).\n"
         f"Current title: {title}\nCurrent description: {description[:1500]}\nViews: {views}\nNiche: {niche}\n"
         'Return ONLY JSON {"title": "<=90 chars", "description": "<=900 chars with 3-5 hashtags at end", "tags": ["<=15 tags"], "reason": "1 line Hinglish"}')
    return json.loads(_text(_gen([{"text": p}], json_mode=True)))

def comment_reply(video_title: str, comment: str) -> str:
    p = (f"You are NISHU replying to a YouTube comment on '{video_title}'. Comment: {comment[:500]}\n"
         "Write one short friendly Hinglish reply (max 20 words, 0-1 emoji). If spam/abuse reply exactly SKIP.")
    return _text(_gen([{"text": p}])).strip()

def image(prompt: str, out_path: str, style: str = "photo", ref_image: str | None = None) -> str:
    """ref_image: a character reference picture — Gemini keeps that exact character in the new scene (consistency)."""
    styles = {"photo": "photorealistic, cinematic lighting", "cartoon": "2D cartoon illustration, bold outlines, bright colors",
              "3d": "3D Pixar-style render, soft lighting", "stock": "photorealistic"}
    parts = []
    if ref_image:
        mime = "image/jpeg" if ref_image.lower().endswith((".jpg", ".jpeg")) else "image/png"
        parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(open(ref_image, "rb").read()).decode()}})
        prompt = "Keep EXACTLY the same character from the reference image (same face, fur, outfit, accessories). " + prompt
    parts.append({"text": f"{prompt}. Style: {styles.get(style, style)}. Vertical 9:16 composition, no text, no logos."})
    j = _gen(parts, model=IMAGE_MODEL, image=True)
    for p in j.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in p:
            open(out_path, "wb").write(base64.b64decode(p["inlineData"]["data"]))
            return out_path
    raise ProviderError("gemini image: no image returned")

def rate_frames(frame_paths: list[str], prompt: str) -> float:
    """0-10 vision rating of how well frames match the prompt and look good. Used in video scoring."""
    parts = [{"text": f"Rate 0-10 how good these frames are for a viral short about: {prompt}. Consider sharpness, artifacts, "
                      "distorted hands/faces, relevance. Reply with only the number."}]
    for f in frame_paths[:4]:
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(open(f, "rb").read()).decode()}})
    m = re.search(r"\d+(\.\d+)?", _text(_gen(parts)))
    return max(0.0, min(10.0, float(m.group(0)))) if m else 5.0
