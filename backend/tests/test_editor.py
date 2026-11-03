import shutil, pytest
from socialcontrol.ff import probe, ffmpeg
from socialcontrol import editor
from socialcontrol.voice import line_words

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

def test_assemble_makes_vertical_captioned_short(tmp_path):
    clip = tmp_path / "c.mp4"; img = tmp_path / "i.png"; voice = tmp_path / "v.wav"; music = tmp_path / "m.wav"
    ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "2", "-pix_fmt", "yuv420p", str(clip)])
    ffmpeg(["-f", "lavfi", "-i", "color=c=0x223355:size=800x800", "-frames:v", "1", str(img)])
    ffmpeg(["-f", "lavfi", "-i", "sine=frequency=300:duration=3", "-ar", "44100", str(voice)])
    ffmpeg(["-f", "lavfi", "-i", "sine=frequency=600:duration=10", "-ar", "44100", str(music)])
    words = line_words({"roman": "Ruko ye dekho", "keywords": ["Ruko"]}, 0, 0.1, 1.4) + line_words({"roman": "AI se fast", "keywords": ["AI"]}, 1, 1.5, 2.9)
    segs = editor.segments_from_words([{"path": str(clip), "type": "video"}, {"path": str(img), "type": "image"}], words)
    out = tmp_path / "out.mp4"
    info = editor.assemble(segs, str(voice), words, str(out), music=str(music), end_card="- N I S H U", tail=1.0)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert 3.8 <= info["duration"] <= 4.3 and info["has_audio"]
