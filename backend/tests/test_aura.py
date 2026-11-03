"""AI Animal Aura Reel template — key-free tests (plan builder, prompts, originality guard, image->video wiring)."""
import shutil, pytest
from socialcontrol import aura, chat, config
from socialcontrol.videogen import orchestrator
from socialcontrol.videogen.providers import Provider, ALL

def test_default_plan_is_20_to_26s_with_4_beat_cut_shots():
    p = aura.build_shot_plan({"animal": "black_lion", "outfit": "black_suit", "locations": ["supercar", "jet", "mansion"]})
    shots = p["shots"]
    assert len(shots) == 4 and 18 <= p["total_seconds"] <= 26
    beat = 60.0 / p["bpm"]
    for i, s in enumerate(shots):
        assert abs(s["duration"] / beat - round(s["duration"] / beat)) < 1e-6      # cut on the beat
        assert s["location"] == ["supercar", "jet", "mansion"][i % 3]              # locations cycle
        assert p["character"]["sheet"] in s["image_prompt"]                        # same character in every shot
        assert "no logos" in s["image_prompt"] and s["gen_seconds"] in (5, 10)
    assert [s["start"] for s in shots] == sorted(s["start"] for s in shots)
    assert "1000" in shots[-1]["line"]["roman"] and "hearts bhejo" in shots[-1]["line"]["roman"]
    assert shots[-1]["move"] == "point"                                            # CTA looks into the lens
    assert "White Lion" in shots[0]["line"]["roman"]                               # rival preset (his script)
    assert all(s["line"]["devanagari"] for s in shots)                             # Hindi voice reads Devanagari

def test_character_reference_is_original_only():
    ch = aura.character(aura.normalize_opts({"animal": "bengal_tiger", "outfit": "sherwani", "name": "Tiger Bhaukaal"}))
    assert "ORIGINAL character 'Tiger Bhaukaal'" in ch["sheet"]
    assert "not based on any existing" in ch["reference_prompt"]

@pytest.mark.parametrize("bad", [
    {"name": "Simba"}, {"name": "Shere Khan 2"}, {"dialogue_mode": "mine", "dialogue": "copy @someone ka lion"},
    {"angle": "https://www.instagram.com/reel/abc"}, {"name": "bilkul waisa hi lion"},
])
def test_guard_blocks_copying_other_characters(bad):
    with pytest.raises(aura.NotOriginal):
        aura.build_shot_plan(bad)

def test_guard_reads_user_blocklist_file():
    (config.DATA / "blocked_characters.txt").write_text("# one name per line\nRaja Babbar Sher\n", "utf-8")
    try:
        with pytest.raises(aura.NotOriginal):
            aura.build_shot_plan({"name": "raja babbar sher"})
        aura.build_shot_plan({"name": "Kaala Badshah"})  # original name passes
    finally:
        (config.DATA / "blocked_characters.txt").unlink()

def test_own_dialogue_and_hearts_and_options():
    p = aura.build_shot_plan({"dialogue_mode": "mine", "dialogue": "Main aa gaya | मैं आ गया\nAb sab dekhenge", "locations": "yacht"})
    assert [s["line"]["roman"] for s in p["shots"]] == ["Main aa gaya", "Ab sab dekhenge"]
    assert p["shots"][0]["line"]["devanagari"] == "मैं आ गया" and p["shots"][1]["line"]["devanagari"] is None
    t = aura.build_shot_plan({"animal": "bengal_tiger", "hearts": 5000, "preset": "king"})
    assert "5000 🧡 orange hearts" in t["cta"] and "5000" in t["shots"][-1]["line"]["roman"]
    with pytest.raises(ValueError): aura.build_shot_plan({"animal": "unicorn"})
    with pytest.raises(ValueError): aura.build_shot_plan({"locations": ["moon"]})
    o = aura.options(); assert {"animals", "outfits", "locations", "presets", "dialogue_modes"} <= set(o)

def test_gemini_dialogue_falls_back_without_key_and_prompt_asks_4_lines():
    o = aura.normalize_opts({"dialogue_mode": "ai", "animal": "white_tiger"})
    assert len(aura.gemini_dialogue(o)) == 4                     # no GEMINI key in tests -> preset
    pr = aura.dialogue_prompt(o)
    assert "exactly 4" in pr and "other creators' characters" in pr and "1000" in pr

def test_to_script_matches_pipeline_shape():
    s = aura.to_script(aura.build_shot_plan({}))
    assert s["template"] == "animal_aura" and len(s["hashtags"]) == 5
    assert all({"roman", "keywords", "image_prompt"} <= set(l) for l in s["lines"])

def test_image_to_video_providers_get_the_still():
    assert {p.name for p in ALL if p.supports_image} == {"veo", "fal", "kling", "runway"}
    seen = {}
    class I2V(Provider):
        supports_image = True
        def __init__(self, name): self.name = name
        def available(self): return True
        def generate(self, prompt, style, seconds, out, image_path=None):
            seen[self.name] = image_path; open(out, "wb").write(b"x"); return out
    ps = [I2V("a"), I2V("b")]
    g = orchestrator.generate_best("p", str(config.DATA / "i2v"), providers=ps, parallel=False,
                                   scorer=lambda path, pr: {"score": 50.0 if "a" in path else 70.0, "reasons": []},
                                   extra={p.name: {"image_path": "still.png"} for p in ps})
    assert seen == {"a": "still.png", "b": "still.png"} and g["best"]["provider"] == "b"

def test_chat_opens_aura_template_inside_create_video():
    out = chat.handle("black lion aura reel banao", lambda t, p: {"id": "j"})
    assert out["goto"] == "create" and out["template"] == "animal_aura"

@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_run_aura_end_to_end_with_demo_assets(monkeypatch):
    from socialcontrol import pipeline, voice, approvals
    from socialcontrol.ff import ffmpeg
    def fake_speak(lines, out, engine="edge", voice="x", gap=0.2):
        words, t = [], 0.0
        for i, l in enumerate(lines):
            d = aura.speech_seconds(l["roman"]); words += voice_mod.line_words(l, i, t, t + d); t += d + gap
        ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=220:duration={t:.2f}", "-ar", "44100", out]); return words
    voice_mod = voice
    monkeypatch.setattr(voice, "speak_lines", fake_speak)
    monkeypatch.setattr(approvals, "ask", lambda *a, **k: True)
    assets = pipeline.make_demo_assets(str(config.DATA / "demo_assets"))
    r = pipeline.run_aura({"animal": "black_lion", "locations": ["supercar", "jet"]}, post=False, demo_assets=assets)
    assert r["ok"], r.get("error")
    from socialcontrol.ff import probe
    info = probe(r["video"])
    assert (info["width"], info["height"]) == (1080, 1920) and 18 <= info["duration"] <= 28 and info["has_audio"]
    assert "hearts bhejo" in r["caption"]
