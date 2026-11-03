import datetime as dt, os
from socialcontrol.scheduler import due
from socialcontrol import approvals, trends, chat, config

def test_scheduler_due_once_per_day():
    now = dt.datetime(2026, 11, 3, 18, 31)
    assert due(now, "18:30", None) and due(now, "18:30", "2026-11-02")
    assert not due(now, "18:30", "2026-11-03") and not due(dt.datetime(2026, 11, 3, 18, 0), "18:30", None)

def test_permission_gate_accept_and_cancel():
    import threading
    a = approvals.request("post", "Post karun?", ["x"]); threading.Timer(0.2, lambda: approvals.decide(a["id"], True)).start()
    assert approvals.wait(a["id"], timeout=5) is True
    b = approvals.request("edit", "Title badlun?", ["y"]); threading.Timer(0.2, lambda: approvals.decide(b["id"], False)).start()
    assert approvals.wait(b["id"], timeout=5) is False
    c = approvals.request("edit", "timeout", ["z"]); assert approvals.wait(c["id"], timeout=0.3) is False

def test_trends_mock_when_everything_offline(monkeypatch):
    for f in ("youtube_trending", "youtube_search", "google_trends", "google_related", "instagram_hashtag"):
        monkeypatch.setattr(trends, f, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    r = trends.find_topics("AI tools")
    assert r["mock"] and r["topics"] and len(r["errors"]) == 5

def test_chat_rules_need_permission_for_settings():
    out = chat.handle("Instagram pe post mat karo", lambda t, p: {"id": "j"})
    assert "approval" in out
    assert config.settings()["post_instagram"] is False  # unchanged until Accept (default False)
    assert approvals.PENDING[out["approval"]]["status"] == "pending"
    assert chat.handle("trend dikhao", lambda t, p: {"id": "j"})["goto"] == "trends"

def test_keys_never_in_repo_listing():
    names = [k["name"] for k in config.keys_status()]
    assert "GEMINI_API_KEY" in names and all("preview" in k for k in config.keys_status())
