"""Template: AI Animal Aura Reel — realistic anthropomorphic animal in a designer suit, luxury scenes,
slow-mo swagger shots, short Hindi attitude dialogue (lip-synced), "1000 hearts bhejo" CTA, ~20-25 s.

Everything in this file is key-free and pure (options, originality guard, dialogue presets, shot plan, prompts),
so it is unit-tested. The pipeline that renders a plan is pipeline.run_aura().

ORIGINAL CHARACTERS ONLY: the template never copies another creator's named character or a film/cartoon character.
check_original() blocks @handles, links, "copy/same as" requests and every name in BLOCKED_NAMES
+ data/blocked_characters.txt (add any creator character names you want blocked, one per line)."""
from __future__ import annotations
import json, math, re

TEMPLATE_ID = "animal_aura"
TEMPLATE_LABEL = "🦁 AI Animal Aura Reel"

ANIMALS = {
    "black_lion":   {"label": "Black Lion",   "hi": "काला शेर",   "desc": "a majestic black-maned lion with dark fur and amber eyes", "heart": "🖤", "heart_word": "black"},
    "white_lion":   {"label": "White Lion",   "hi": "सफ़ेद शेर",  "desc": "a majestic white lion with a thick snow-white mane and ice-blue eyes", "heart": "🤍", "heart_word": "white"},
    "golden_lion":  {"label": "Golden Lion",  "hi": "शेर",       "desc": "a powerful golden lion with a full dark-gold mane", "heart": "💛", "heart_word": "yellow"},
    "bengal_tiger": {"label": "Bengal Tiger", "hi": "बाघ",       "desc": "a muscular Bengal tiger with deep orange fur and bold black stripes", "heart": "🧡", "heart_word": "orange"},
    "white_tiger":  {"label": "White Tiger",  "hi": "सफ़ेद बाघ", "desc": "a white tiger with black stripes and piercing blue eyes", "heart": "🤍", "heart_word": "white"},
    "black_panther_cat": {"label": "Black Panther (animal)", "hi": "काला तेंदुआ", "desc": "a sleek black leopard (melanistic panther) with glowing green eyes", "heart": "🖤", "heart_word": "black"},
    "snow_leopard": {"label": "Snow Leopard", "hi": "हिम तेंदुआ", "desc": "a snow leopard with smoky grey spotted fur and pale green eyes", "heart": "🤍", "heart_word": "white"},
    "wolf":         {"label": "Grey Wolf",    "hi": "भेड़िया",    "desc": "a large grey wolf with silver fur and sharp golden eyes", "heart": "🩶", "heart_word": "grey"},
    "gorilla":      {"label": "Silverback Gorilla", "hi": "गोरिल्ला", "desc": "a huge silverback gorilla with a calm, intimidating stare", "heart": "🖤", "heart_word": "black"},
    "eagle":        {"label": "Golden Eagle", "hi": "बाज़",       "desc": "a golden eagle with sharp feathers and a fierce gaze", "heart": "💛", "heart_word": "yellow"},
}

OUTFITS = {
    "black_suit":  {"label": "Black designer suit", "desc": "a tailored black designer three-piece suit, black silk shirt, thick gold Cuban chain, gold watch, dark aviator sunglasses"},
    "white_suit":  {"label": "White designer suit", "desc": "a tailored ivory-white designer suit, open-collar shirt, gold chain, diamond watch, gold-rim sunglasses"},
    "navy_tux":    {"label": "Navy tuxedo",         "desc": "a midnight-navy velvet tuxedo with satin lapels, bow tie, gold chain, black sunglasses"},
    "leather":     {"label": "Leather jacket",      "desc": "a premium black leather jacket over a black tee, layered gold chains, black sunglasses"},
    "sherwani":    {"label": "Royal sherwani",      "desc": "a royal black-and-gold embroidered sherwani, gold chain, kada bracelet, dark sunglasses"},
}

LOCATIONS = {
    "yacht":     {"label": "Luxury yacht",  "desc": "on the deck of a white superyacht on a turquoise sea at golden hour"},
    "mansion":   {"label": "Mansion",       "desc": "in front of a modern glass mansion with an infinity pool at dusk"},
    "supercar":  {"label": "Supercar",      "desc": "next to a matte-black supercar with scissor doors open, on a wet city street with neon reflections"},
    "jet":       {"label": "Private jet",   "desc": "on the stairs of a private jet on a runway at sunset, wind blowing"},
    "rooftop":   {"label": "City rooftop",  "desc": "on a skyscraper rooftop helipad overlooking a glittering Mumbai skyline at night"},
    "throne":    {"label": "Throne room",   "desc": "seated on a black-and-gold throne in a dark marble palace hall with warm spotlights"},
    "casino":    {"label": "Luxury lounge", "desc": "in a dim luxury lounge with gold lights and smoke haze"},
}

# shot "moves": slow-mo swagger actions that read as aura. Talking shots end facing camera so lip-sync is clean.
MOVES = [
    {"id": "glasses_off", "action": "slowly takes off the sunglasses and stares into the camera", "camera": "slow push-in, low angle", "effect": "slowmo"},
    {"id": "walk",        "action": "walks toward the camera in slow motion with confident swagger", "camera": "tracking shot, low angle", "effect": "slowmo"},
    {"id": "key_spin",    "action": "spins a car key on one finger and smirks", "camera": "medium close-up, shallow depth of field", "effect": "zoom"},
    {"id": "glasses_on",  "action": "puts the sunglasses back on, suit jacket flowing in the wind", "camera": "slow orbit around the character", "effect": "slowmo"},
    {"id": "point",       "action": "looks straight into the lens and points at the camera", "camera": "close-up, eye level, static", "effect": "flash"},
]

BLOCKED_NAMES = [  # well-known film/cartoon/brand animal characters — never copy these
    "simba", "mufasa", "scar", "nala", "shere khan", "bagheera", "baloo", "akela", "tigress", "po ", "king julien",
    "alex the lion", "tony the tiger", "tigger", "aslan", "rafiki", "kung fu panda", "zootopia", "madagascar",
    "lion king", "jungle book", "sonic", "pikachu", "garfield", "puss in boots",
]

class NotOriginal(ValueError):
    pass

def _extra_blocked() -> list[str]:
    try:
        from . import config
        p = config.DATA / "blocked_characters.txt"
        return [l.strip().lower() for l in p.read_text("utf-8").splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []
    except Exception:
        return []

def check_original(*texts: str) -> None:
    """Raise NotOriginal if any text asks to copy another creator's/film's character."""
    blocked = BLOCKED_NAMES + _extra_blocked()
    for t in texts:
        if not t: continue
        low = " " + t.lower() + " "
        if re.search(r"https?://|www\.|instagram\.com|youtube\.com|tiktok\.com", low):
            raise NotOriginal("Link mat do — template dusre creator ki reel copy nahi karta. Apna idea likho 🙂")
        if re.search(r"(?<![\w.])@[a-z0-9_.]{2,}", low):
            raise NotOriginal("@handle mat do — dusre creator ka character copy nahi hoga. Apna original character banao.")
        if re.search(r"\b(copy|same as|hubahu|bilkul waisa|waisa hi|clone|replica)\b", low):
            raise NotOriginal("Copy/clone nahi — sirf original character. Animal, outfit, location khud chuno.")
        for n in blocked:
            n = n.lower()
            if n and re.search(r"(?<![a-z])" + re.escape(n.strip()) + r"(?![a-z])", low):
                raise NotOriginal(f"'{n.strip()}' kisi aur ka character hai — original naam/character use karo.")

# ---------- dialogue ----------
PRESETS = {
    # NIRBHAY's own approved script (Nov 3, 2026)
    "rival_rich": [
        ("Suna hai aajkal {rival} ka aura bahut badh gaya hai...", "सुना है आजकल {rival_hi} का ऑरा बहुत बढ़ गया है...", ["aura"]),
        ("Kya sach me wo mujhse zyada amir hai? Uski poori zindagi ki kamai... meri ek gaadi ki keemat hai.",
         "क्या सच में वो मुझसे ज़्यादा अमीर है? उसकी पूरी ज़िंदगी की कमाई... मेरी एक गाड़ी की कीमत है।", ["amir", "gaadi"]),
        ("Paisa sabke paas hota hai... par aura? Aura sirf {me} ka chalta hai.", "पैसा सबके पास होता है... पर ऑरा? ऑरा सिर्फ़ {me_hi} का चलता है।", ["aura", "{me_first}"]),
        ("Agar {me} ka aura zyada hai, to {n} {heart} {heart_word} hearts bhejo!", "अगर {me_hi} का ऑरा ज़्यादा है, तो {n_hi} {heart_word} hearts भेजो!", ["{n}", "hearts"]),
    ],
    "king": [
        ("Jungle me sher bahut hain... par raja sirf ek.", "जंगल में शेर बहुत हैं... पर राजा सिर्फ़ एक।", ["raja"]),
        ("Log mehnat dekhte hain, main result dikhata hoon.", "लोग मेहनत देखते हैं, मैं result दिखाता हूँ।", ["result"]),
        ("Ye gaadi, ye jet... sab apne dum pe.", "ये गाड़ी, ये जेट... सब अपने दम पे।", ["dum"]),
        ("{me} ka aura pasand aaya? To {n} {heart} {heart_word} hearts bhejo!", "{me_hi} का ऑरा पसंद आया? तो {n_hi} {heart_word} hearts भेजो!", ["{n}", "hearts"]),
    ],
}
NUM_HI = {"100": "सौ", "500": "पाँच सौ", "1000": "एक हज़ार", "5000": "पाँच हज़ार", "10000": "दस हज़ार"}

def default_dialogue(animal: str, preset: str = "rival_rich", rival: str | None = None, hearts: int = 1000) -> list[dict]:
    a = ANIMALS[animal]
    rv = rival or ("White Lion" if animal != "white_lion" else "Black Lion")
    rv_key = next((k for k, v in ANIMALS.items() if v["label"] == rv), None)
    f = {"me": a["label"], "me_hi": a["hi"], "me_first": a["label"].split()[0], "rival": rv,
         "rival_hi": ANIMALS[rv_key]["hi"] if rv_key else rv, "n": str(hearts), "n_hi": NUM_HI.get(str(hearts), str(hearts)),
         "heart": a["heart"], "heart_word": a["heart_word"]}
    out = []
    for r, d, k in PRESETS.get(preset, PRESETS["rival_rich"]):
        out.append({"roman": r.format(**f), "devanagari": d.format(**f), "keywords": [x.format(**f) for x in k]})
    return out

def parse_dialogue(text: str) -> list[dict]:
    """User's own lines: one per line (Roman Hinglish). 'roman | देवनागरी' gives the voice a Devanagari version."""
    out = []
    for raw in (text or "").splitlines():
        raw = raw.strip(" -•\t")
        if not raw: continue
        roman, _, dev = raw.partition("|")
        roman = roman.strip(); words = [w.strip(".,!?…") for w in roman.split()]
        kw = sorted(words, key=len, reverse=True)[:1]
        out.append({"roman": roman, "devanagari": dev.strip() or None, "keywords": kw})
    return out[:6]

DIALOGUE_PROMPT = """Write exactly 4 short Hindi attitude lines (Roman Hinglish) for a viral Instagram "aura" reel.
Speaker: an ORIGINAL anthropomorphic {animal} in {outfit}, rich and confident, in luxury places ({places}).
{angle}Line 1 = hook (rival / rumour / question), lines 2-3 = flex + attitude punchline, line 4 = CTA asking for
{n} {heart_word} hearts {heart} in comments. Max 14 words per line. No real people, no brand names, no other creators' characters.
Return ONLY JSON: {{"lines": [{{"roman": "...", "devanagari": "same line in Devanagari for the Hindi voice", "keywords": ["1-2 words to highlight"]}}]}}"""

def dialogue_prompt(opts: dict) -> str:
    a, o = ANIMALS[opts["animal"]], OUTFITS[opts["outfit"]]
    places = ", ".join(LOCATIONS[l]["label"] for l in opts["locations"])
    angle = f"Angle: {opts['angle']}. " if opts.get("angle") else ""
    return DIALOGUE_PROMPT.format(animal=a["label"].lower(), outfit=o["label"].lower(), places=places, angle=angle,
                                  n=opts.get("hearts", 1000), heart_word=a["heart_word"], heart=a["heart"])

def gemini_dialogue(opts: dict) -> list[dict]:
    """Gemini writes 4 lines; falls back to the preset when no key / bad answer."""
    from . import ai, config
    if not config.has("GEMINI_API_KEY"):
        return default_dialogue(opts["animal"], opts.get("preset", "rival_rich"), opts.get("rival"), opts.get("hearts", 1000))
    j = ai._gen([{"text": dialogue_prompt(opts)}], json_mode=True)
    lines = json.loads(re.sub(r"^```(json)?|```$", "", ai._text(j).strip()))["lines"][:4]
    lines = [{"roman": l["roman"], "devanagari": l.get("devanagari"), "keywords": l.get("keywords", [])[:2]} for l in lines]
    check_original(*[l["roman"] for l in lines])
    return lines

# ---------- character + shot plan ----------
def normalize_opts(opts: dict | None) -> dict:
    o = dict(opts or {})
    o.setdefault("animal", "black_lion"); o.setdefault("outfit", "black_suit")
    locs = o.get("locations") or ["supercar", "jet", "mansion"]
    if isinstance(locs, str): locs = [x.strip() for x in locs.split(",") if x.strip()]
    o["locations"] = locs
    o.setdefault("hearts", 1000); o.setdefault("seconds", 22); o.setdefault("bpm", 100)
    o.setdefault("dialogue_mode", "preset")  # preset | ai | mine
    for k, table in (("animal", ANIMALS), ("outfit", OUTFITS)):
        if o[k] not in table: raise ValueError(f"unknown {k}: {o[k]} (choose: {', '.join(table)})")
    bad = [l for l in o["locations"] if l not in LOCATIONS]
    if bad or not o["locations"]: raise ValueError(f"unknown location(s): {bad} (choose: {', '.join(LOCATIONS)})")
    o["seconds"] = max(15, min(30, int(o["seconds"])))
    check_original(o.get("name", ""), o.get("dialogue", ""), o.get("angle", ""), o.get("rival", "") or "")
    return o

def character(opts: dict) -> dict:
    a, o = ANIMALS[opts["animal"]], OUTFITS[opts["outfit"]]
    name = (opts.get("name") or a["label"]).strip()
    sheet = (f"ORIGINAL character '{name}': {a['desc']}, anthropomorphic, standing upright with a human-like muscular build, "
             f"wearing {o['desc']}. Ultra-realistic fur detail, cinematic lighting, confident 'aura' attitude")
    return {"name": name, "animal": opts["animal"], "outfit": opts["outfit"], "sheet": sheet,
            "reference_prompt": (f"Full-body character reference portrait of {sheet}. Plain dark studio background, front view, "
                                 "sharp focus, 9:16. Original design, not based on any existing movie, cartoon or creator character. No text, no logos."),
            "guard": "original-only"}

def speech_seconds(roman: str) -> float:
    """Rough Hindi TTS length (Edge voice at +8%): ~3 words/s + short pauses on '...' and '?'."""
    w = len(roman.split()); pauses = roman.count("...") + roman.count("?") + roman.count("!") * 0.5
    return round(w / 3.0 + 0.3 * pauses + 0.3, 2)

def snap(sec: float, bpm: int, beats_per_unit: int = 1) -> float:
    unit = 60.0 / bpm * beats_per_unit
    return round(max(unit, math.ceil(sec / unit - 1e-9) * unit), 3)

def build_shot_plan(opts: dict | None, lines: list[dict] | None = None) -> dict:
    """One talking shot per dialogue line, each at a luxury location, cut on the beat, total ~seconds."""
    opts = normalize_opts(opts)
    if lines is None:
        lines = (parse_dialogue(opts["dialogue"]) if opts["dialogue_mode"] == "mine" and opts.get("dialogue")
                 else default_dialogue(opts["animal"], opts.get("preset", "rival_rich"), opts.get("rival"), opts["hearts"]))
    if not lines: raise ValueError("dialogue khali hai — kam se kam 1 line do")
    check_original(*[l["roman"] for l in lines])
    ch = character(opts); a = ANIMALS[opts["animal"]]
    raw = [speech_seconds(l["roman"]) for l in lines]
    target = opts["seconds"] - 2.2  # end card tail
    scale = max(1.0, target / sum(raw))  # stretch with pauses/slow-mo to reach the target length, never squeeze speech
    shots, t = [], 0.0
    for i, (l, r) in enumerate(zip(lines, raw)):
        loc_key = opts["locations"][i % len(opts["locations"])]; loc = LOCATIONS[loc_key]
        move = MOVES[-1] if i == len(lines) - 1 else MOVES[i % (len(MOVES) - 1)]
        dur = snap(r * scale, opts["bpm"])
        scene = f"{ch['sheet']}, {loc['desc']}"
        shots.append({
            "n": i + 1, "start": round(t, 3), "duration": dur, "location": loc_key, "location_label": loc["label"],
            "move": move["id"], "action": move["action"], "camera": move["camera"], "effect": move["effect"],
            "line": l, "lipsync": True, "gen_seconds": 5 if dur <= 5.2 else 10,
            "image_prompt": f"{scene}. The character {move['action']}. {move['camera']}, photorealistic, cinematic, 9:16, no text, no logos.",
            "video_prompt": (f"The same character {move['action']}, mouth moving as if speaking, {move['camera']}, "
                             f"{'slow motion, ' if move['effect'] == 'slowmo' else ''}cinematic, realistic fur and fabric motion, keep the character identical."),
        })
        t += dur
    total = round(t + 2.2, 2)
    warn = None if total <= 26 else f"Dialogue lamba hai (~{total:.0f}s). 20-25s ke liye lines chhoti karo."
    cta = f"{opts['hearts']} {a['heart']} {a['heart_word']} hearts bhejo"
    title = f"{ch['name']} ka aura 😎{a['heart']} | {cta}"
    return {"template": TEMPLATE_ID, "character": ch, "shots": shots, "bpm": opts["bpm"], "total_seconds": total,
            "voice": opts.get("voice", "hi-IN-MadhurNeural"), "cta": cta, "title": title[:90],
            "description": f"{ch['name']} ka aura kaisa laga? 👇\nComment me {cta}! 🔥",
            "hashtags": ["#aura", "#lion" if "lion" in opts["animal"] else "#animals", "#viral", "#reels", "#attitude"],
            "music_note": "Trending sound: Instagram app me post karte waqt IG library se lagao (licensed). App me apni royalty-free beat assets/music/ me rakho.",
            "warning": warn, "originality": "Original character only — kisi creator/film ka character copy nahi."}

def to_script(plan: dict) -> dict:
    """Plan -> the pipeline's script shape (lines with roman/devanagari/keywords/image_prompt)."""
    lines = [{**s["line"], "image_prompt": s["image_prompt"], "broll": s["location_label"]} for s in plan["shots"]]
    return {"title": plan["title"], "lines": lines, "description": plan["description"], "hashtags": plan["hashtags"],
            "tags": ["aura", "ai animal", "lion", "attitude", "hindi", "reels", "shorts", "viral", "ai video", "javagoat9"],
            "offline": True, "template": TEMPLATE_ID}

def options() -> dict:
    t = lambda d: [{"id": k, "label": v["label"]} for k, v in d.items()]
    return {"template": TEMPLATE_ID, "label": TEMPLATE_LABEL, "animals": t(ANIMALS), "outfits": t(OUTFITS), "locations": t(LOCATIONS),
            "presets": [{"id": "rival_rich", "label": "Rival vs me (aura/amir)"}, {"id": "king", "label": "Raja sirf ek"}],
            "dialogue_modes": [{"id": "preset", "label": "Ready script"}, {"id": "ai", "label": "Gemini 4 lines likhe"}, {"id": "mine", "label": "Apni lines"}],
            "note": "Sirf original characters. Dusre creators ke named characters / reels copy nahi hote."}
