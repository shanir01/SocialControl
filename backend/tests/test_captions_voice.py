from socialcontrol.captions import chunks, build_ass, ts
from socialcontrol.voice import line_words

def test_line_words_span_and_highlight():
    ws = line_words({"roman": "AI tools se kaam fast karo", "keywords": ["AI", "fast"]}, 0, 1.0, 4.0)
    assert ws[0]["start"] == 1.0 and abs(ws[-1]["end"] - 4.0) < 0.01
    assert [w["word"] for w in ws if w["highlight"]] == ["AI", "fast"]
    assert all(a["end"] <= b["start"] + 1e-6 for a, b in zip(ws, ws[1:]))

def test_chunks_do_not_cross_lines():
    ws = line_words({"roman": "ek do teen char", "keywords": []}, 0, 0, 2) + line_words({"roman": "paanch chhe", "keywords": []}, 1, 2, 3)
    cs = chunks(ws, max_words=3)
    assert all(len({w["line"] for w in c}) == 1 for c in cs) and all(len(c) <= 3 for c in cs)

def test_ass_has_yellow_keyword_and_end_card():
    ws = line_words({"roman": "Comment karo AI", "keywords": ["AI"]}, 0, 0, 1.5)
    ass = build_ass(ws, "- N I S H U", 4.0)
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "\\c&H0000FFFF&\\fscx118\\fscy118}AI" in ass        # yellow keyword (popped while spoken)
    assert "- N I S H U" in ass and ts(1.8) in ass
    assert ass.count("Dialogue:") == 3 + 1

def test_ts_format():
    assert ts(0) == "0:00:00.00" and ts(61.256) == "0:01:01.26"
