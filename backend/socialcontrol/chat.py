"""AI chat panel: you tell the app what to do / what not to do; it acts ONLY on the app's own features.
Anything that changes something goes through the permission card (approvals)."""
from __future__ import annotations
import json, re
from . import config, approvals

SYSTEM = """You are the assistant inside the SocialControl app (Hinglish). Map the user's message to ONE action. Return ONLY JSON:
{"action": "find_trends"|"scan"|"create_video"|"set_settings"|"answer", "args": {...}, "reply": "short Hinglish reply"}
find_trends args {"niche"}; scan args {"channel"}; create_video args {"topic"};
set_settings args {"changes": {key: value}} using ONLY these keys: SETTINGS_KEYS. Example: "music mat lagao" is not a key -> answer.
"ye mat karo" style negatives usually map to switching a boolean setting off. Never invent actions outside the app."""

RULES = [
    (r"trend|viral kya|kya chal raha", "find_trends"),
    (r"scan|channel check|analy[sz]", "scan"),
    (r"video (bana|bnao|banao|create)|banao video|make video", "create_video"),
]

def _rules(msg: str) -> dict:
    m = msg.lower()
    for pat, act in RULES:
        if re.search(pat, m):
            topic = re.sub(r"(pe|par|ke upar)?\s*(ek )?video (bana\w*|bnao|create)|please|plz", "", msg, flags=re.I).strip(" .,!")
            ch = re.search(r"@[\w.\-]+", msg)
            return {"action": act, "args": {"topic": topic, "niche": topic, "channel": ch.group(0) if ch else ""}, "reply": "Theek hai 👍"}
    toggles = {"youtube": "post_youtube", "instagram": "post_instagram", "insta": "post_instagram", "pinterest": "post_pinterest",
               "ai video": "use_ai_video", "auto": "scheduler_on"}
    for word, key in toggles.items():
        if word in m and re.search(r"mat|band|off|nahi|na kare", m):
            return {"action": "set_settings", "args": {"changes": {key: False}}, "reply": f"{key} band kar dunga — pehle permission card dekh lo."}
        if word in m and re.search(r"\bon\b|chalu|karo|start", m):
            return {"action": "set_settings", "args": {"changes": {key: True}}, "reply": f"{key} chalu kar dunga — permission card dekh lo."}
    return {"action": "answer", "args": {}, "reply": "Main ye kar sakta hoon: trend dhundna, channel scan, video banana, settings on/off. Thoda clear bolo 🙂"}

def interpret(msg: str) -> dict:
    if config.has("GEMINI_API_KEY"):
        try:
            from . import ai
            sys = SYSTEM.replace("SETTINGS_KEYS", ", ".join(config.DEFAULT_SETTINGS))
            return json.loads(ai._text(ai._gen([{"text": sys + "\nUser: " + msg}], json_mode=True)))
        except Exception:
            pass
    return _rules(msg)

def handle(msg: str, start_job) -> dict:
    it = interpret(msg); act, args = it.get("action"), it.get("args", {}) or {}
    out = {"reply": it.get("reply", "OK"), "done": []}
    if act == "find_trends":
        out["goto"] = "trends"
    elif act == "scan":
        if args.get("channel"): config.save_settings({"channel_to_scan": args["channel"]})
        out["goto"] = "scan"
    elif act == "create_video":
        j = start_job(args.get("topic") or None, None)   # the pipeline itself asks permission before making/posting
        out.update(job=j["id"], topic=args.get("topic"), reply=out["reply"] + " Permission card aa raha hai, Accept karoge to video banegi.")
    elif act == "set_settings":
        ch = {k: v for k, v in (args.get("changes") or {}).items() if k in config.DEFAULT_SETTINGS}
        if ch:
            a = approvals.request("settings", "Settings badlunga", [f"{k}: {config.settings().get(k)} → {v}" for k, v in ch.items()], "chat")
            a["apply"] = ch; out["approval"] = a["id"]
    return out
