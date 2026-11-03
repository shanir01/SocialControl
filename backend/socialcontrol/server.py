"""Local server: dashboard (PWA) + API on http://localhost:8765. The desktop app is just a window on this.
Phone on the same Wi-Fi opens http://<PC-IP>:8765 and enters the PIN shown in Settings (localhost needs no PIN)."""
from __future__ import annotations
import json, os, secrets, socket, threading, time, uuid
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from . import config, trends, channel_scan, pipeline, tracker, scheduler, ai, approvals, chat

WEB = config.ROOT / "web"
app = FastAPI(title="SocialControl", docs_url=None, redoc_url=None)
JOBS: dict[str, dict] = {}
FC = {"active": False, "shared": False, "step": "idle", "stepIndex": -1, "url": "", "log": [], "topics": [], "stop": False, "session_deleted": None, "frame_t": 0}
FRAME = {"jpg": b""}

def pin() -> str:
    s = config._read()
    if not s.get("SC_PIN"):
        config.save_settings({"SC_PIN": f"{secrets.randbelow(10**6):06d}"}); s = config._read()
    return s["SC_PIN"]

def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"

@app.middleware("http")
async def guard(request: Request, call_next):
    host = request.client.host if request.client else ""
    local = host in ("127.0.0.1", "::1", "localhost", "testclient")
    path = request.url.path
    if not local and (path.startswith("/api") or path.startswith("/media")) and path != "/api/login":
        if request.cookies.get("sc_pin") != pin() and request.headers.get("x-vy-pin") != pin():
            return JSONResponse({"error": "pin required"}, status_code=401)
    return await call_next(request)

@app.post("/api/login")
def login(body: dict = Body(...)):
    if str(body.get("pin")) != pin(): raise HTTPException(401, "wrong pin")
    r = JSONResponse({"ok": True}); r.set_cookie("sc_pin", pin(), max_age=3600 * 24 * 30, httponly=True, samesite="strict"); return r

@app.get("/api/status")
def status(request: Request):
    ks = config.keys_status(); local = request.client and request.client.host in ("127.0.0.1", "::1", "testclient")
    from . import poster
    last = sorted(pipeline.RUNS.glob("*/result.json"))[-1:] if pipeline.RUNS.exists() else []
    return {"keys_set": sum(k["set"] for k in ks), "keys_total": len(ks), "youtube_connected": poster.yt_connected(),
            "settings": config.settings(), "last_run": json.loads(last[0].read_text("utf-8")) if last else None,
            "phone": {"url": f"http://{lan_ip()}:{os.environ.get('SC_PORT', '8765')}", "pin": pin() if local else None}}

@app.get("/api/settings")
def get_settings(): return config.settings()

@app.post("/api/settings")
def set_settings(body: dict = Body(...)):
    clean = {k: v for k, v in body.items() if k in config.DEFAULT_SETTINGS}
    return config.save_settings(clean)

@app.get("/api/keys")
def get_keys(): return config.keys_status()

@app.post("/api/keys")
def set_keys(body: dict = Body(...)):
    clean = {k: str(v).strip() for k, v in body.items() if k in config.KEY_NAMES and v is not None}
    config.save_settings(clean); return config.keys_status()

@app.get("/api/trends")
def api_trends(niche: str = "", region: str = ""):
    return trends.find_topics(niche or None, region or None)

@app.get("/api/scan")
def api_scan(channel: str = "", platform: str = "youtube"):
    try:
        if platform == "instagram":
            return channel_scan.scan_instagram(channel or None)
        return channel_scan.scan(channel or config.settings()["channel_to_scan"])
    except Exception as e:
        raise HTTPException(400, str(e))

def _job(topic, post, template=None, aura_opts=None):
    jid = uuid.uuid4().hex[:8]; JOBS[jid] = {"id": jid, "topic": topic, "template": template or "normal", "status": "running", "events": [], "result": None}
    def go():
        ev = lambda e: JOBS[jid]["events"].append(e)
        r = (pipeline.run_aura(aura_opts, post=post, on_event=ev) if template == "animal_aura"
             else pipeline.run_pipeline(topic or None, post=post, on_event=ev))
        JOBS[jid].update(status="done" if r["ok"] else "failed", result={k: v for k, v in r.items() if k != "events"})
    threading.Thread(target=go, daemon=True).start(); return JOBS[jid]

@app.post("/api/create")
def create(body: dict = Body(default={})):
    if body.get("template") == "animal_aura":
        from . import aura
        try: aura.normalize_opts(body.get("aura"))  # validate + originality guard before starting
        except ValueError as e: raise HTTPException(400, str(e))
        return _job(None, body.get("post"), "animal_aura", body.get("aura"))
    return _job(body.get("topic"), body.get("post"))

# --- AI Animal Aura Reel template (lives inside Create Video) ---
@app.get("/api/aura/options")
def aura_options():
    from . import aura
    return aura.options()

@app.post("/api/aura/plan")
def aura_plan(body: dict = Body(default={})):
    """Preview: shot plan + prompts. Gemini writes the 4 lines only when dialogue_mode='ai' and the key is set."""
    from . import aura
    try:
        o = aura.normalize_opts(body)
        return aura.build_shot_plan(o, aura.gemini_dialogue(o) if o["dialogue_mode"] == "ai" else None)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/jobs/{jid}")
def job(jid: str):
    if jid not in JOBS: raise HTTPException(404)
    return JOBS[jid]

@app.get("/api/runs")
def runs():
    out = []
    for d in sorted(pipeline.RUNS.glob("*"), reverse=True)[:20] if pipeline.RUNS.exists() else []:
        r = json.loads((d / "result.json").read_text("utf-8")) if (d / "result.json").exists() else {"run": d.name}
        if (d / "final.mp4").exists(): r["video_url"] = f"/media/runs/{d.name}/final.mp4"
        out.append(r)
    return out

@app.get("/media/runs/{rid}/final.mp4")
def media_file(rid: str):
    p = pipeline.RUNS / rid / "final.mp4"
    if not p.exists() or ".." in rid: raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4")

@app.get("/api/tracker")
def api_tracker(): return tracker.report()

@app.post("/api/tracker/refresh")
def api_tracker_refresh(): return tracker.refresh()

@app.post("/api/youtube/connect")
def yt_connect():
    from . import poster
    try:
        poster.yt_service(interactive=True); return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.get("/api/youtube/videos")
def yt_videos(limit: int = 50):
    from . import poster
    try: return poster.yt_my_videos(limit)
    except Exception as e: raise HTTPException(400, str(e))

@app.post("/api/youtube/update")
def yt_update(body: dict = Body(...)):
    from . import poster
    return poster.yt_update_video(body["id"], body.get("title"), body.get("description"), body.get("tags"))

@app.post("/api/ai/metadata")
def ai_meta(body: dict = Body(...)):
    try: return ai.video_metadata(body.get("title", ""), body.get("description", ""), int(body.get("views", 0)), config.settings()["niche"])
    except Exception as e: raise HTTPException(400, str(e))

# ---- Full Control relay (desktop app drives; phone watches + can Stop) ----
@app.get("/api/fc/state")
def fc_state(): return {**FC, "log": FC["log"][-200:]}

@app.post("/api/fc/state")
def fc_set(body: dict = Body(...)):
    for k in ("active", "shared", "step", "stepIndex", "url", "topics", "session_deleted"):
        if k in body: FC[k] = body[k]
    if body.get("log"): FC["log"].append({"t": time.strftime("%H:%M:%S"), "msg": body["log"]})
    if body.get("reset"): FC.update(log=[], topics=[], stop=False, session_deleted=None, stepIndex=-1)
    return {"stop": FC["stop"]}

@app.post("/api/fc/stop")
def fc_stop():
    FC["stop"] = True; FC["log"].append({"t": time.strftime("%H:%M:%S"), "msg": "STOP pressed — control wapas user ko"}); return {"ok": True}

@app.post("/api/fc/frame")
async def fc_frame_in(request: Request):
    FRAME["jpg"] = await request.body(); FC["frame_t"] = time.time(); return {"ok": True}

@app.get("/api/fc/frame")
def fc_frame_out():
    return Response(FRAME["jpg"], media_type="image/jpeg", headers={"Cache-Control": "no-store"})

@app.post("/api/fc/topics")
def fc_topics(body: dict = Body(...)):
    """Full Control hands over the topic list; the app makes (and, per Settings, posts) videos on the top N."""
    FC["topics"] = body.get("topics", [])
    n = int(config.settings().get("fc_videos_per_session", 2))
    jobs = []
    def chain():
        for t in FC["topics"][:n]:
            j = _job(t["keyword"] if isinstance(t, dict) else t, None); jobs.append(j["id"])
            while JOBS[j["id"]]["status"] == "running": time.sleep(2)
    threading.Thread(target=chain, daemon=True).start()
    return {"queued": min(n, len(FC["topics"]))}

@app.get("/api/approvals")
def approvals_list(all: bool = False):
    return [{k: v for k, v in a.items() if k != "apply"} for a in approvals.listing(all)]

@app.post("/api/approvals/{aid}")
def approvals_decide(aid: str, body: dict = Body(...)):
    a = approvals.decide(aid, bool(body.get("accept")))
    if a.get("status") == "accepted" and a.get("apply"):   # settings changes asked from chat
        config.save_settings(a["apply"])
    return {k: v for k, v in a.items() if k != "apply"}

@app.post("/api/approvals")
def approvals_new(body: dict = Body(...)):
    """Desktop Full Control asks here before each change; it then polls GET /api/approvals/{id}."""
    return approvals.request(body.get("kind", "fullcontrol"), body.get("title", ""), body.get("details", []), body.get("source", "fullcontrol"))

@app.get("/api/approvals/{aid}")
def approvals_get(aid: str):
    a = approvals.PENDING.get(aid)
    if not a: raise HTTPException(404)
    return {k: v for k, v in a.items() if k != "apply"}

@app.post("/api/chat")
def api_chat(body: dict = Body(...)):
    return chat.handle(str(body.get("message", ""))[:1000], _job)

@app.get("/")
def index(): return FileResponse(WEB / "index.html")

app.mount("/", StaticFiles(directory=str(WEB)), name="web")

def serve(port=8765, host="0.0.0.0"):
    import uvicorn
    os.environ["SC_PORT"] = str(port)
    scheduler.start(lambda: pipeline.run_pipeline())
    print(f"SocialControl: http://localhost:{port}   phone: http://{lan_ip()}:{port}  PIN {pin()}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")
