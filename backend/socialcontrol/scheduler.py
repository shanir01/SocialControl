"""In-app daily scheduler (runs while the app is open). For 24x7 use the GitHub Actions workflow."""
from __future__ import annotations
import datetime as dt, json, threading, time
from . import config

STATE = config.DATA / "scheduler.json"
_thread = None

def _last():
    try: return json.loads(STATE.read_text()).get("last_date")
    except Exception: return None

def due(now: dt.datetime, daily_time: str, last_date: str | None) -> bool:
    hh, mm = [int(x) for x in daily_time.split(":")]
    return now.strftime("%Y-%m-%d") != last_date and (now.hour, now.minute) >= (hh, mm)

def loop(run_fn):
    while True:
        s = config.settings()
        if s.get("scheduler_on") and due(dt.datetime.now(), s.get("daily_time", "18:30"), _last()):
            STATE.write_text(json.dumps({"last_date": dt.datetime.now().strftime("%Y-%m-%d")}))
            try: run_fn()
            except Exception as e: print("scheduler run failed:", e)
        time.sleep(30)

def start(run_fn):
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=loop, args=(run_fn,), daemon=True); _thread.start()
