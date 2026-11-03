import os, tempfile
from socialcontrol.videogen.scoring import score_metrics
from socialcontrol.videogen import orchestrator
from socialcontrol.videogen.providers import Provider
from socialcontrol.http import ProviderError

def test_score_good_vs_bad():
    good = score_metrics({"duration": 6, "width": 1080, "height": 1920, "black_ratio": 0})
    low = score_metrics({"duration": 6, "width": 480, "height": 854, "black_ratio": 0})
    black = score_metrics({"duration": 6, "width": 1080, "height": 1920, "black_ratio": 0.5})
    short = score_metrics({"duration": 1, "width": 1080, "height": 1920, "black_ratio": 0})
    wrong = score_metrics({"duration": 6, "width": 1920, "height": 1080, "black_ratio": 0})
    assert good["score"] > low["score"] and good["score"] > black["score"] and good["score"] > short["score"] and good["score"] > wrong["score"]
    assert score_metrics({"duration": 0, "width": 0, "height": 0})["score"] == 0

def test_vision_adds_points():
    base = {"duration": 6, "width": 1080, "height": 1920, "black_ratio": 0}
    assert score_metrics(base, vision=9)["score"] > score_metrics(base, vision=2)["score"]

class Fake(Provider):
    def __init__(self, name, score=None, error=None, quota=False):
        self.name, self._score, self._err, self._quota = name, score, error, quota
    def available(self): return True
    def generate(self, prompt, style, seconds, out):
        if self._err: raise ProviderError(self._err, quota=self._quota)
        open(out, "wb").write(b"x"); return out

def scorer_for(table):
    return lambda path, prompt: {"score": table[os.path.basename(path).split(".")[0]], "reasons": ["test"]}

def test_picks_best_of_all(tmp_path):
    ps = [Fake("a", 60), Fake("b", 88), Fake("c", 70)]
    r = orchestrator.generate_best("x", str(tmp_path), providers=ps, scorer=scorer_for({"a": 60, "b": 88, "c": 70}))
    assert r["best"]["provider"] == "b" and r["tried"] == ["a", "b", "c"] and len(r["results"]) == 3

def test_fallback_when_provider_fails_and_quota_cooldown(tmp_path):
    ps = [Fake("veo_t", error="429 quota", quota=True), Fake("kling_t", error="500 boom"), Fake("stock_t", 50)]
    r = orchestrator.generate_best("x", str(tmp_path), providers=ps, scorer=scorer_for({"stock_t": 50}))
    assert r["best"]["provider"] == "stock_t"
    assert set(r["errors"]) == {"veo_t", "kling_t"}
    assert orchestrator.cooled("veo_t") and not orchestrator.cooled("kling_t")
    # next run skips the cooled provider automatically
    r2 = orchestrator.generate_best("x", str(tmp_path), providers=ps, scorer=scorer_for({"stock_t": 50}))
    assert "veo_t" not in r2["tried"]

def test_all_fail_or_too_low_returns_none(tmp_path):
    ps = [Fake("p1", error="down"), Fake("p2", 10)]
    r = orchestrator.generate_best("x", str(tmp_path), providers=ps, scorer=scorer_for({"p2": 10}), min_score=35)
    assert r["best"] is None and r["results"][0]["provider"] == "p2"
