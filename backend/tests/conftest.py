import os, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("SC_DATA_DIR", tempfile.mkdtemp(prefix="sc_test_"))
for k in ["YOUTUBE_API_KEY", "GEMINI_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY", "FAL_KEY", "RUNWAY_API_KEY", "LUMA_API_KEY", "KLING_ACCESS_KEY", "KLING_SECRET_KEY"]:
    os.environ.pop(k, None)
