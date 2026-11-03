"""python -m socialcontrol serve | run | demo | trends | scan @channel"""
import argparse, json, sys

def main():
    ap = argparse.ArgumentParser(prog="socialcontrol")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, default=8765); s.add_argument("--host", default="0.0.0.0")
    r = sub.add_parser("run", help="full pipeline once (used by scheduler / GitHub Actions)")
    r.add_argument("--topic"); r.add_argument("--post", action="store_true"); r.add_argument("--no-post", action="store_true")
    sub.add_parser("demo", help="key-free demo: local test visuals + free Edge TTS voice -> 9:16 captioned mp4")
    t = sub.add_parser("trends"); t.add_argument("--niche", default=None)
    c = sub.add_parser("scan"); c.add_argument("channel")
    a = ap.parse_args()
    import os
    if a.cmd in ("run", "demo"):
        os.environ.setdefault("SC_CLI", "1")
    if a.cmd == "demo":
        os.environ["SC_AUTO_APPROVE"] = "1"   # demo never posts; nothing to approve
    if a.cmd == "serve":
        from .server import serve; serve(a.port, a.host)
    elif a.cmd == "run":
        from .pipeline import run_pipeline
        res = run_pipeline(a.topic, post=True if a.post else (False if a.no_post else None))
        print(json.dumps({k: v for k, v in res.items() if k != "events"}, indent=2, ensure_ascii=False)); sys.exit(0 if res["ok"] else 1)
    elif a.cmd == "demo":
        from .pipeline import run_pipeline, make_demo_assets
        from . import config
        assets = make_demo_assets(str(config.DATA / "demo_assets"))
        res = run_pipeline("YouTube pe viral kaise ho", post=False, demo_assets=assets)
        print(json.dumps({k: v for k, v in res.items() if k != "events"}, indent=2, ensure_ascii=False)); sys.exit(0 if res["ok"] else 1)
    elif a.cmd == "trends":
        from .trends import find_topics
        print(json.dumps(find_topics(a.niche), indent=2, ensure_ascii=False))
    elif a.cmd == "scan":
        from .channel_scan import scan
        d = scan(a.channel); d.pop("videos", None); print(json.dumps(d, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
