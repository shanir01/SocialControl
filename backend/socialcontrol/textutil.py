import re
STOP = set("""a an the and or of to in on for with is are was were be by at from this that it its as you your my me i we our
ka ki ke ko se me mein hai hain ho hota hoti tha thi kya kaise kyu kyun aur bhi ye yeh wo woh ek do par pe na nahi
video videos shorts short reel reels new full part official viral trending ft feat vs l hindi episode""".split())

def keywords(text: str) -> list[str]:
    text = re.sub(r"#\w+", " ", text or "")
    ws = re.findall(r"[\w\u0900-\u097F]+", text.lower())
    return [w for w in ws if len(w) > 2 and w not in STOP and not w.isdigit()]
