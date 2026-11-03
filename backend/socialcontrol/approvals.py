"""Permission gate: before the AI changes anything (makes/edits a video, changes title/description/tags,
Full Control actions, posting, settings) it posts a card in the chat panel. Accept -> it acts. Cancel -> nothing changes."""
from __future__ import annotations
import os, threading, time, uuid

PENDING: dict[str, dict] = {}
_cv = threading.Condition()

def request(kind: str, title: str, details: list[str] | str, source: str = "app") -> dict:
    a = {"id": uuid.uuid4().hex[:10], "kind": kind, "title": title, "details": details if isinstance(details, list) else [details],
         "source": source, "status": "pending", "created": time.strftime("%H:%M:%S")}
    with _cv:
        PENDING[a["id"]] = a
    return a

def decide(aid: str, accept: bool) -> dict:
    with _cv:
        a = PENDING.get(aid)
        if not a or a["status"] != "pending":
            return a or {}
        a["status"] = "accepted" if accept else "cancelled"; a["decided"] = time.strftime("%H:%M:%S")
        _cv.notify_all()
    return a

def wait(aid: str, timeout: float = 6 * 3600) -> bool:
    end = time.time() + timeout
    with _cv:
        while PENDING[aid]["status"] == "pending":
            left = end - time.time()
            if left <= 0:
                PENDING[aid]["status"] = "cancelled"; PENDING[aid]["why"] = "timeout"; return False
            _cv.wait(min(left, 5))
    return PENDING[aid]["status"] == "accepted"

def ask(kind, title, details, source="app", timeout=6 * 3600) -> bool:
    """Blocking ask. Headless runs (GitHub Actions) set SC_AUTO_APPROVE=1 because nobody is there to tap."""
    if os.environ.get("SC_AUTO_APPROVE") == "1":
        return True
    if os.environ.get("SC_CLI") == "1":          # terminal run: ask right here
        import sys
        if not sys.stdin.isatty():
            return False
        print(f"\n[PERMISSION] {title}\n  - " + "\n  - ".join(details if isinstance(details, list) else [details]))
        return input("Accept? (y/n): ").strip().lower().startswith("y")
    return wait(request(kind, title, details, source)["id"], timeout)

def listing(include_done=False) -> list[dict]:
    rows = sorted(PENDING.values(), key=lambda a: a["created"])
    return rows if include_done else [a for a in rows if a["status"] == "pending"]
