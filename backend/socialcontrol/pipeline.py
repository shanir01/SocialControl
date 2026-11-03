"""End-to-end: topic -> script -> visuals (stock / AI image / best AI video) -> voice -> edit -> post -> track."""
from __future__ import annotations
import datetime as dt, json, os, pathlib, traceback
from . import config, trends, ai, media, voice, editor, tracker, channel_scan, approvals
from .http import ProviderError

RUNS = config.DATA / "runs"

class Cancelled(Exception):
    pass

class Run:
    def __init__(self, on_event=None):
        self.id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = RUNS / self.id; self.dir.mkdir(parents=True, exist_ok=True)
        self.events, self.on_event = [], on_event
    def log(self, step, msg, **extra):
        e = {"t": dt.datetime.now().strftime("%H:%M:%S"), "step": step, "msg": msg, **extra}
        self.events.append(e)
        with open(self.dir / "log.jsonl", "a", encoding="utf-8") as f: f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"[{e['t']}] {step}: {msg}", flush=True)
        if self.on_event: self.on_event(e)

def pick_topic(run: Run, s: dict) -> str:
    """Mix: channel's best-performing topics (what already works for you) + today's trends."""
    best_kw = []
    if s.get("channel_to_scan"):
        try:
            sc = channel_scan.scan(s["channel_to_scan"], limit=200)
            best_kw = [t["keyword"] for t in sc["top_topics"][:5]]
            run.log("scan", f"{sc['channel']}: {sc['total_videos']} videos, top topics {best_kw}")
        except Exception as e:
            run.log("scan", f"skipped: {e}")
    t = trends.find_topics(niche=s["niche"] + ("," + ",".join(best_kw) if best_kw else ""))
    run.log("trends", f"{len(t['topics'])} topics" + (" (MOCK — add keys for live trends)" if t["mock"] else ""), errors=t["errors"])
    top = t["topics"][0]["title"] if t["topics"] else s["niche"]
    return top

def run_pipeline(topic: str | None = None, post: bool | None = None, on_event=None, demo_assets: list[dict] | None = None) -> dict:
    s = config.settings(); run = Run(on_event)
    try:
        topic = topic or pick_topic(run, s)
        run.log("topic", topic)
        script = ai.write_script(topic)
        run.log("script", script["title"] + (" (offline template — add GEMINI_API_KEY)" if script.get("offline") else ""))
        (run.dir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), "utf-8")
        lines = script["lines"]
        if not approvals.ask("create", f"Video banaun? “{script['title']}”",
                             [f"Topic: {topic}", f"{len(lines)} lines script, style {s['video_style']}, voice {s['voice']}",
                              "Hook: " + lines[0]["roman"]], "pipeline"):
            run.log("cancelled", "Aapne Cancel kiya — kuch nahi badla"); raise Cancelled()

        # visuals per line
        visuals = []
        for i, line in enumerate(lines):
            if demo_assets:
                visuals.append(demo_assets[i % len(demo_assets)]); continue
            v = None
            if s.get("use_ai_video") and i < 3:  # AI video for the hook lines (costly) — best of all providers
                from .videogen import generate_best, available_providers
                if available_providers():
                    extra = {}
                    if any(p.name == "runway" for p in available_providers()):
                        try: extra["runway"] = {"image_path": media.ai_image(line["image_prompt"], str(run.dir / f"first{i}.png"), s["video_style"])["path"]}
                        except Exception: pass
                    g = generate_best(line["image_prompt"], str(run.dir / f"aivideo{i}"), style=s["video_style"], extra=extra)
                    run.log("ai_video", f"line {i+1}: tried {g['tried']}", best=(g["best"] or {}).get("provider"),
                            scores={r["provider"]: r["score"] for r in g["results"]}, errors=g["errors"])
                    if g["best"]: v = {"path": g["best"]["path"], "type": "video", "source": g["best"]["provider"]}
            if v is None:
                v = media.get_visual(line, str(run.dir / f"v{i}"), style=s["video_style"])
            run.log("media", f"line {i+1}: {v['source']}")
            visuals.append(v)

        # voice
        vpath = str(run.dir / "voice.wav")
        words = voice.speak_lines(lines, vpath, engine=s["voice_engine"], voice=s["voice"])
        run.log("voice", f"{len(words)} caption words, voice {s['voice']}")

        # edit
        out = str(run.dir / "final.mp4")
        info = editor.assemble(editor.segments_from_words(visuals, words), vpath, words, out,
                               music=media.local_music(), end_card=s.get("end_card"))
        run.log("edit", f"{info['width']}x{info['height']} {info['duration']:.1f}s", path=out)

        caption = f"{script['title']}\n\n{script['description']}\n\n{' '.join(script['hashtags'][:5])}"
        (run.dir / "caption.txt").write_text(caption, "utf-8")
        posts = []
        do_post = s["post_youtube"] or s["post_instagram"] or s["post_pinterest"] if post is None else post
        targets = [n for f, n in (("post_youtube", "YouTube"), ("post_instagram", "Instagram"), ("post_pinterest", "Pinterest")) if s.get(f)]
        if do_post and targets and not approvals.ask("post", f"Post karun? {' + '.join(targets)}",
                                                     [f"Title: {script['title']}", f"Hashtags: {' '.join(script['hashtags'][:5])}",
                                                      f"Privacy (YouTube): {s['privacy']}"], "pipeline"):
            run.log("post", "Post cancel — video sirf PC pe saved hai"); do_post = False
        if do_post:
            from . import poster
            for flag, fn in (("post_youtube", lambda: poster.youtube_upload(out, script["title"], caption, script["tags"], s["privacy"])),
                             ("post_instagram", lambda: poster.instagram_reel(out, caption)),
                             ("post_pinterest", lambda: poster.pinterest_video_pin(out, script["title"], caption))):
                if s.get(flag):
                    try:
                        p = fn(); posts.append(p); tracker.record(p, script["title"], run.id); run.log("post", f"{p['platform']}: {p['url']}")
                    except Exception as e:
                        run.log("post", f"{flag} failed: {e}")
        result = {"ok": True, "run": run.id, "video": out, "title": script["title"], "caption": caption, "posts": posts, "events": run.events}
    except Cancelled:
        result = {"ok": False, "run": run.id, "error": "cancelled by you", "events": run.events}
    except Exception as e:
        run.log("error", str(e), trace=traceback.format_exc()[-1500:])
        result = {"ok": False, "run": run.id, "error": str(e), "events": run.events}
    (run.dir / "result.json").write_text(json.dumps({k: v for k, v in result.items() if k != "events"}, indent=2, ensure_ascii=False), "utf-8")
    return result

def make_demo_assets(folder: str) -> list[dict]:
    """Key-free local test visuals (generated, copyright-free): 2 moving clips + 2 images."""
    from .ff import ffmpeg
    os.makedirs(folder, exist_ok=True); out = []
    specs = [("clip_a.mp4", "testsrc2=size=1280x720:rate=30", "video"), ("clip_b.mp4", "mandelbrot=size=720x1280:rate=30", "video"),
             ("img_a.png", "gradients=size=1080x1920:c0=0x1b1035:c1=0xff2e88:speed=0.02", "image"),
             ("img_b.png", "gradients=size=1080x1920:c0=0x07203a:c1=0x00e5ff:speed=0.02", "image")]
    for name, src, kind in specs:
        p = os.path.join(folder, name)
        if not os.path.exists(p):
            if kind == "video": ffmpeg(["-f", "lavfi", "-i", src, "-t", "4", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", p])
            else: ffmpeg(["-f", "lavfi", "-i", src, "-frames:v", "1", p])
        out.append({"path": p, "type": kind, "source": "local-test"})
    return out
