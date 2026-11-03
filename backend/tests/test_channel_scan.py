from socialcontrol.channel_scan import bucket_of, bucketize, top_topics, _handle

def test_bucket_labels():
    assert bucket_of(50) == "<100"
    assert bucket_of(100) == "100+"
    assert bucket_of(250) == "200+"
    assert bucket_of(499) == "400+"
    assert bucket_of(999) == "500+"
    assert bucket_of(1500) == "1K+"
    assert bucket_of(25_000) == "10K+"
    assert bucket_of(2_500_000) == "1M+"

def test_bucketize_cumulative():
    vids = [{"views": v, "title": "x"} for v in (50, 120, 230, 650, 1200, 15000)]
    b = bucketize(vids)
    assert b["exact"]["<100"] == 1 and b["exact"]["1K+"] == 1 and b["exact"]["10K+"] == 1
    assert b["cumulative"]["100+"] == 5 and b["cumulative"]["500+"] == 3 and b["cumulative"]["1K+"] == 2 and b["cumulative"]["10K+"] == 1

def test_top_topics_prefers_high_view_keywords():
    vids = [{"title": "free AI tools for students", "views": 9000}, {"title": "best free AI tools 2026", "views": 7000},
            {"title": "my vlog day", "views": 40}, {"title": "free AI tools hindi", "views": 5000}, {"title": "cooking vlog", "views": 30}]
    tt = top_topics(vids, top_share=0.6)
    words = [t["keyword"] for t in tt]
    assert words[0] in ("free", "tools") and "vlog" not in words[:2]

def test_handle_parsing():
    assert _handle("https://www.youtube.com/@javagoat9/videos") == "@javagoat9"
    assert _handle("javagoat9") == "@javagoat9"
    assert _handle("https://youtube.com/channel/UC123abc") == "UC123abc"
