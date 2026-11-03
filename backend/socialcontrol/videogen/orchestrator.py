"""Generate with EVERY configured provider, score each result, keep the best.
A provider that fails or hits quota is skipped (quota -> cooled down for COOLDOWN_H hours) and the next one is used."""
from __future__ import annotations
import json, os, time, concurrent.futures as cf
from .. import config
from ..http import ProviderError
from .scoring import score_file

STATE = config.DATA / "provider_state.json"
COOLDOWN_H = 12

def _state():
    try: return json.loads(STATE.read_text())
    except Exception: return {}

def _cool(name, why):
    s = _state(); s[name] = {"until": time.time() + COOLDOWN_H * 3600, "why": why[:200]}
    STATE.write_text(json.dumps(s, indent=2))

def cooled(name): return _state().get(name, {}).get("until", 0) > time.time()

def available_providers(providers=None):
    from .providers import ALL
    ps = providers if providers is not None else ALL
    return [p for p in ps if p.available() and not cooled(p.name)]

def generate_best(prompt: str, out_dir: str, style="photo", seconds=5, providers=None, scorer=None,
                  parallel=True, min_score=35.0, extra: dict | None = None) -> dict:
    """Returns {best: {provider, path, score, reasons} | None, results: [...], errors: {name: msg}}.
    scorer(path, prompt) -> {score, reasons}; defaults to heuristic + optional Gemini vision."""
    os.makedirs(out_dir, exist_ok=True)
    scorer = scorer or (lambda p, pr: score_file(p, pr, use_vision=config.has("GEMINI_API_KEY")))
    ps = available_providers(providers)
    results, errors = [], {}
    def run(p):
        out = os.path.join(out_dir, f"{p.name}.mp4")
        kw = (extra or {}).get(p.name, {})
        path = p.generate(prompt, style, seconds, out, **kw)
        sc = scorer(path, prompt)
        return {"provider": p.name, "path": path, **sc}
    if parallel and len(ps) > 1:
        with cf.ThreadPoolExecutor(max_workers=len(ps)) as ex:
            futs = {ex.submit(run, p): p for p in ps}
            for f in cf.as_completed(futs):
                p = futs[f]
                try: results.append(f.result())
                except Exception as e: _fail(p, e, errors)
    else:
        for p in ps:
            try: results.append(run(p))
            except Exception as e: _fail(p, e, errors)
    good = sorted([r for r in results if r["score"] >= min_score], key=lambda r: r["score"], reverse=True)
    return {"best": good[0] if good else None, "results": sorted(results, key=lambda r: -r["score"]), "errors": errors,
            "tried": [p.name for p in ps]}

def _fail(p, e, errors):
    errors[p.name] = str(e)[:300]
    if isinstance(e, ProviderError) and e.quota:
        _cool(p.name, str(e))
