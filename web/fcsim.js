// Demo-only Full Control simulation (the real one runs in the desktop app's embedded browser).
// Shows the flow with the same visible animated cursor the desktop agent injects into the page.
(function () {
  if (!new URLSearchParams(location.search).has("demo") && !window.SC_FORCE_DEMO) return;
  const S = { active: false, shared: false, stepIndex: -1, log: [], topics: [], url: "youtube.com" };
  let timers = [];
  const view = () => document.querySelector("#fcView");
  const log = m => S.log.push({ t: new Date().toTimeString().slice(0, 8), msg: m });
  const CUR = `<svg class="cursor" id="simCur" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.6L21 10.8z" fill="#fff" stroke="#ff2e88" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  function moveTo(sel) {
    const v = view(), el = v.querySelector(sel), c = v.querySelector("#simCur"); if (!el || !c) return;
    const a = v.getBoundingClientRect(), b = el.getBoundingClientRect();
    c.style.transform = `translate(${b.left - a.left + b.width / 2}px,${b.top - a.top + b.height / 2}px)`;
  }
  function click() { const c = view().querySelector("#simCur"); c.classList.remove("click"); void c.offsetWidth; c.classList.add("click"); }
  const ROWS = (window.SC_DEMO_SCAN_ROWS || []);
  function paint(html) { const old = view().querySelector("#simCur"); const keep = old ? old.style.transform : ""; 
    view().querySelectorAll(".mock").forEach(n => n.remove()); view().insertAdjacentHTML("beforeend", `<div class="mock">${html}</div>`);
    if (!view().querySelector("#simCur")) view().insertAdjacentHTML("beforeend", CUR); else view().querySelector("#simCur").style.transform = keep; }
  const at = (ms, fn) => timers.push(setTimeout(fn, ms));
  function start() {
    Object.assign(S, { active: true, shared: false, stepIndex: -1, log: [], topics: [], url: "youtube.com" });
    document.querySelector("#fcEmpty").hidden = true; document.querySelector("#fcFrame").hidden = true;
    const rows = ROWS.filter(v => !/phish/i.test(v.title)).slice(0, 7);
    paint(`<div class="ms"><div class="yt"><b>▶</b>YouTube</div><div class="on">Home</div><div>Shorts</div><div>Subscriptions</div></div>
      <div class="mm"><div style="display:flex;justify-content:flex-end"><span id="signin" style="border:1px solid #3ea6ff;color:#3ea6ff;border-radius:18px;padding:5px 12px">👤 Sign in</span></div>
      <h4 style="margin-top:20px">Recommended</h4>${[1,2,3].map(() => `<div class="vr"><i></i><span style="height:10px;background:#2a2a2a;border-radius:4px"></span><span></span><span></span></div>`).join("")}</div>`);
    log("Private session bana (memory only, kuch save nahi hoga)"); log("YouTube khola");
    at(600, () => moveTo("#signin")); at(1500, () => { click(); S.stepIndex = 0; log("Sign in pe click kiya — ab aap login karo"); });
    at(2100, () => { S.url = "accounts.google.com"; paint(`<div class="login"><div class="box"><div class="g">Google</div><div style="font-size:20px;margin-top:8px">Sign in</div><div style="color:#5f6368;font-size:12px">to continue to YouTube</div>
      <input id="em" value="" placeholder="Email or phone"><div style="color:#1a73e8;font-size:12px">Aap khud type karte ho — app password kabhi nahi padhta</div></div></div>`);
      log("Google ka apna login page — user typing…"); });
    at(2600, () => { const e = view().querySelector("#em"); if (e) e.value = "nishu••••@gmail.com"; });
    at(3400, () => { S.stepIndex = 1; log("Login ho gaya ✓ (password app ne nahi dekha)"); });
    at(3900, () => { S.shared = true; S.stepIndex = 2; log("Share Control dabaya — control AI ke paas"); });
    at(4400, () => { S.url = "studio.youtube.com/channel/…/videos"; S.stepIndex = 3; log("YouTube Studio khola → Content");
      paint(`<div class="ms"><div class="yt"><b>▶</b>Studio</div><div>Dashboard</div><div class="on" id="content">Content</div><div>Analytics</div><div>Comments</div></div>
        <div class="mm"><h4>Channel content · Java Goat</h4><div class="vr" style="color:#aaa"><span></span><span>Video</span><span>Views</span><span>Likes</span></div>
        ${rows.map((v, i) => `<div class="vr" id="r${i}"><i></i><span>${v.title.slice(0, 46)}</span><span>${v.views.toLocaleString()}</span><span>${Math.round(v.views / 40)}</span></div>`).join("")}</div>`);
      moveTo("#content"); });
    rows.forEach((v, i) => at(5000 + i * 650, () => { view().querySelectorAll(".vr.hl").forEach(n => n.classList.remove("hl")); const r = view().querySelector("#r" + i); r && r.classList.add("hl"); moveTo("#r" + i); log(`Analyse: “${v.title.slice(0, 40)}…” — ${v.views.toLocaleString()} views`); }));
    const T = 5000 + rows.length * 650;
    at(T, () => { S.stepIndex = 4; log(`${window.SC_DEMO_TOTAL || 24} videos analyse ho gayi`); });
    at(T + 600, () => { S.stepIndex = 5; S.topics = (window.SC_DEMO_TOPICS || []).slice(0, 6); log("Topic list bani → app ko di"); });
    at(T + 1200, () => { log("Permission card chat me — Accept karoge to videos banengi"); });
    at(T + 6000, () => { S.stepIndex = 6; log("2 videos queue me (Create Video me dikhenge)"); });
    at(T + 7500, end);
  }
  function end() { timers.forEach(clearTimeout); timers = []; S.active = false; S.shared = false; S.stepIndex = 7; S.url = "—";
    log("Session deleted ✅ (cookies, storage, cache sab saaf)"); view().querySelectorAll(".mock,#simCur").forEach(n => n.remove());
    const e = document.querySelector("#fcEmpty"); e.hidden = false; e.innerHTML = "<b>Session deleted ✅</b><span>Login, cookies, cache — sab mita diya</span>"; }
  window.SC_FC_SIM = { state: () => S, start, stop: () => { log("STOP — control wapas aapke paas"); end(); } };
})();
