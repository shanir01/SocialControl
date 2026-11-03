// SocialControl dashboard — one file, no framework. Works in the desktop window, a browser, and on phone (PWA).
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const DEMO = new URLSearchParams(location.search).has("demo") || !!window.SC_FORCE_DEMO;
const DESKTOP = !!window.sc;                       // Electron preload exposes window.sc
const fmt = n => n >= 1e6 ? (n/1e6).toFixed(1)+"M" : n >= 1e3 ? (n/1e3).toFixed(1)+"K" : String(n ?? 0);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const toast = m => { const t = $("#toast"); t.textContent = m; t.classList.add("on"); setTimeout(() => t.classList.remove("on"), 2600); };

async function api(path, opt = {}) {
  if (DEMO && window.SC_DEMO) { const d = SC_DEMO(path, opt); if (d !== undefined) return d; }
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opt, body: opt.body && JSON.stringify(opt.body) });
  if (r.status === 401) { $("#pinGate").hidden = false; throw new Error("pin"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}

// ---------- navigation ----------
const TABS = [["dashboard","◆","Home"],["trends","↗","Trends"],["scan","◎","Scan"],["create","✦","Create"],["control","⌘","Control"],["settings","⚙","Settings"]];
$("#tabbar").innerHTML = TABS.map(([id,i,l]) => `<a href="#${id}" data-tab="${id}"><i>${i}</i>${l}</a>`).join("");
function route() {
  const id = (location.hash || "#dashboard").slice(1);
  $$(".view").forEach(v => v.classList.toggle("on", v.id === id));
  $$("[data-tab]").forEach(a => a.classList.toggle("on", a.dataset.tab === id));
  ({dashboard: loadDashboard, settings: loadSettings, control: fcInit, scan: () => !$("#scanOut").innerHTML && doScan()})[id]?.();
  if (DESKTOP) window.sc.fullControl.visible(id === "control");
}
addEventListener("hashchange", route);

// ---------- dashboard (views tracker lives here) ----------
async function loadDashboard() {
  const [st, tr] = await Promise.all([api("/api/status"), api("/api/tracker")]);
  const pp = tr.per_platform || {};
  $("#stats").innerHTML = `
    <div class="stat hero"><small>Total views</small><b>${fmt(tr.total_views)}</b><em>${tr.videos?.length || 0} videos posted</em></div>
    <div class="stat"><small>YouTube views</small><b>${fmt(pp.youtube?.views)}</b><em>${pp.youtube?.videos || 0} shorts</em></div>
    <div class="stat"><small>Instagram views</small><b>${fmt(pp.instagram?.views)}</b><em>${pp.instagram?.videos || 0} reels</em></div>
    <div class="stat"><small>Keys ready</small><b>${st.keys_set}/${st.keys_total}</b><em style="color:var(--mut)">Settings me add karo</em></div>`;
  const vids = tr.videos || [];
  $("#recent").innerHTML = vids.length ? vids.slice(0, 6).map(v => `
    <div class="row"><div class="thumb">▶</div><div class="t"><b>${esc(v.title)}</b><small>${esc(v.posted_at?.replace("T"," ").slice(0,16))}</small></div>
    <span class="pill ${v.platform==="youtube"?"yt":"ig"}">${v.platform==="youtube"?"YouTube":"Instagram"}</span><span class="num">${fmt(v.views)}</span></div>`).join("")
    : `<div class="empty">Abhi koi post nahi. Create Video se pehli video banao ✦</div>`;
  const s = st.settings;
  $("#autorun").innerHTML = `<div class="row"><div class="t"><b>${s.scheduler_on ? "Roz " + s.daily_time + " baje" : "Band hai"}</b><small>Niche: ${esc(s.niche)}</small></div><span class="pill ${s.scheduler_on?"gt":""}">${s.scheduler_on?"ON":"OFF"}</span></div>
    <div class="row"><div class="t"><b>Auto post</b><small>${[s.post_youtube&&"YouTube",s.post_instagram&&"Instagram",s.post_pinterest&&"Pinterest"].filter(Boolean).join(" + ") || "Sirf video banegi, post nahi"}</small></div></div>`;
  const need = [["YOUTUBE_API_KEY","YouTube"],["GEMINI_API_KEY","Gemini AI"],["PEXELS_API_KEY","Pexels"]];
  const keys = await api("/api/keys"); const set = Object.fromEntries(keys.map(k => [k.name, k.set]));
  $("#setup").innerHTML = need.map(([k,l]) => `<div class="row"><div class="t"><b>${l}</b></div><span class="pill ${set[k]?"gt":""}">${set[k]?"✓ ready":"key chahiye"}</span></div>`).join("")
    + `<div class="row"><div class="t"><b>YouTube upload</b></div><span class="pill ${st.youtube_connected?"gt":""}">${st.youtube_connected?"✓ connected":"connect karo"}</span></div>`;
  $("#sideFoot").innerHTML = `Status<br><b>${st.keys_set}/${st.keys_total}</b> keys · YouTube ${st.youtube_connected ? "connected" : "not connected"}`;
}
$("#refreshViews").onclick = async () => { await api("/api/tracker/refresh", {method:"POST"}); loadDashboard(); toast("Views updated"); };

// ---------- trends ----------
const srcPill = s => s.startsWith("youtube") ? `<span class="pill yt">YouTube</span>` : s === "instagram" ? `<span class="pill ig">Instagram</span>` : s.startsWith("google") ? `<span class="pill gt">Google Trends</span>` : `<span class="pill">${s}</span>`;
async function findTrends() {
  $("#trendList").innerHTML = `<div class="empty">Dhundh raha hoon…</div>`;
  const d = await api("/api/trends?niche=" + encodeURIComponent($("#niche").value));
  const max = Math.max(...d.topics.map(t => t.score), 1);
  $("#hotkw").innerHTML = d.hot_keywords.slice(0, 12).map(k => `<span class="chip"># ${esc(k)}</span>`).join("");
  $("#trendList").innerHTML = d.topics.map(t => `<div class="topic"><div class="meta">${srcPill(t.source)}<span>${t.views ? fmt(t.views) + " views/searches" : ""}</span></div>
    <b>${esc(t.title)}</b><div class="score"><i style="width:${(t.score/max*100).toFixed(0)}%"></i></div>
    <div class="act"><small class="note">viral score ${t.score}</small><button class="btn sm" data-topic="${esc(t.title)}">→ Create</button></div></div>`).join("")
    + (d.mock ? `<p class="note">Demo topics — live trends ke liye Settings me YouTube key daalo.</p>` : "");
}
$("#findTrends").onclick = findTrends;
document.addEventListener("click", e => { const b = e.target.closest("[data-topic]"); if (b) { $("#topic").value = b.dataset.topic; location.hash = "#create"; } });

// ---------- channel scan ----------
async function doScan() {
  const ch = $("#chan").value || (await api("/api/settings")).channel_to_scan;
  $("#chan").value = ch; $("#scanOut").innerHTML = `<div class="empty">${esc(ch)} scan ho raha hai…</div>`;
  try {
    const d = await api("/api/scan?channel=" + encodeURIComponent(ch));
    const cum = d.buckets.cumulative; const ks = Object.keys(cum).filter(k => cum[k] > 0 || ["100+","200+","300+","400+","500+","1K+"].includes(k)).slice(0, 9);
    const mx = Math.max(...ks.map(k => cum[k]), 1);
    $("#scanOut").innerHTML = `
      <div class="sum"><div class="stat hero"><small>${esc(d.channel)}</small><b>${d.total_videos}</b><em>videos</em></div>
        <div class="stat"><small>Total views</small><b>${fmt(d.total_views)}</b><em>${d.subscribers ? fmt(d.subscribers)+" subscribers" : "via public list"}</em></div>
        <div class="stat"><small>Best video</small><b>${fmt(d.top_videos[0]?.views)}</b><em>${esc((d.top_videos[0]?.title||"").slice(0,28))}</em></div></div>
      <div class="grid2"><div class="card"><h3>Kitni videos kitne views ke upar</h3><div class="buckets">${ks.map(k => `<div class="bk"><b>${cum[k]}</b><i style="height:${Math.max(3, cum[k]/mx*130)}px"></i><small>${k}</small></div>`).join("")}</div></div>
      <div class="card"><h3>Top topics (sabse zyada chale)</h3>${d.top_topics.slice(0,6).map(t => `<div class="row"><div class="t"><b>${esc(t.keyword)}</b><small>${t.videos} videos · ${fmt(t.views)} views</small></div><button class="btn sm" data-topic="${esc(t.examples[0]||t.keyword)}">→ Create</button></div>`).join("") || `<div class="empty">—</div>`}</div></div>
      <div class="card"><h3>Top videos</h3>${d.top_videos.slice(0,8).map((v,i) => `<div class="row"><div class="thumb">${i+1}</div><div class="t"><b>${esc(v.title)}</b><small>${esc(v.type||"")}</small></div><span class="num">${fmt(v.views)}</span></div>`).join("")}</div>`;
  } catch (e) { $("#scanOut").innerHTML = `<div class="empty">Scan nahi hua: ${esc(e.message)}</div>`; }
}
$("#doScan").onclick = doScan;

// ---------- create ----------
const STEPSETS = {
  normal: [["topic","Topic"],["script","Script + title"],["media","Clips / AI visuals"],["voice","Voiceover"],["edit","Edit + captions"],["post","Post"]],
  animal_aura: [["plan","Shot plan"],["voice","Hindi voice"],["character","Character image"],["shots","Shot stills"],["ai_video","Image → video"],["lipsync","Lip-sync"],["edit","Edit + captions"]],
};
let TPL = "normal", STEPS = STEPSETS.normal;
function paintSteps(events, done) {
  const seen = new Set(events.map(e => TPL === "normal" && e.step === "ai_video" ? "media" : e.step));
  let cur = STEPS.findIndex(([k]) => !seen.has(k));
  $("#steps").innerHTML = STEPS.map(([k,l],i) => `<li class="${seen.has(k) || (done && i < STEPS.length) ? "done" : i === cur ? "now" : ""}">${l}</li>`).join("");
  $("#runlog").innerHTML = events.map(e => `<div><span>${e.t}</span>${esc(e.msg)}</div>`).join("");
  $("#runlog").scrollTop = 1e9;
}
async function startJob(body, msg) {
  let j; try { j = await api("/api/create", { method: "POST", body }); } catch (e) { toast(e.message); return; }
  toast(msg); paintSteps([], false); $("#steps").scrollIntoView({ behavior: "smooth", block: "center" });
  const poll = setInterval(async () => {
    const s = await api("/api/jobs/" + j.id); paintSteps(s.events, s.status === "done");
    if (s.status !== "running") { clearInterval(poll); if (s.result?.ok) showResult(s.result); else toast("Error: " + (s.result?.error || "")); }
  }, 1500);
}
const create = () => startJob({ topic: $("#topic").value || null }, "Video ban rahi hai…");
function showResult(r) {
  $("#captionBox").innerHTML = `<div class="cap">${esc(r.caption)}</div>`;
  if (DEMO && r.template === "animal_aura") { $("#player").removeAttribute("src"); $("#phEmpty").hidden = false;
    $("#phEmpty").innerHTML = "🦁 Demo mode<br><small>Asli reel aapki keys (Gemini + Veo/Kling/fal) se PC pe banegi</small>"; return; }
  $("#player").src = DEMO ? "demo-reel.mp4" : `/media/runs/${r.run}/final.mp4`; $("#phEmpty").hidden = true;
}
$("#go").onclick = create;

// AI Animal Aura Reel — a template inside Create Video (no separate menu)
function setTemplate(t) {
  TPL = t; STEPS = STEPSETS[t] || STEPSETS.normal;
  $$("#tplSeg button").forEach(b => b.classList.toggle("on", b.dataset.tpl === t));
  $("#tplNormal").hidden = t !== "normal"; $("#tplAura").hidden = t !== "animal_aura";
  $("#createSub").textContent = t === "normal" ? "Topic do (ya khali chhodo, AI khud trending topic chunega)."
    : "Suit, sunglasses, gold chain wala AI animal + luxury scenes + Hindi attitude dialogue + lip-sync, ~20-25 sec.";
  paintSteps([], false); if (t === "animal_aura") loadAura();
}
$$("#tplSeg button").forEach(b => b.onclick = () => setTemplate(b.dataset.tpl));
let AURA = null, auLocs = ["supercar", "jet", "mansion"];
async function loadAura() {
  if (AURA) return; AURA = await api("/api/aura/options");
  const opts = (sel, list, v) => { $(sel).innerHTML = list.map(o => `<option value="${o.id}"${o.id === v ? " selected" : ""}>${esc(o.label)}</option>`).join(""); };
  opts("#auAnimal", AURA.animals, "black_lion"); opts("#auOutfit", AURA.outfits, "black_suit");
  opts("#auMode", AURA.dialogue_modes, "preset"); opts("#auPreset", AURA.presets, "rival_rich");
  paintLocs(); $("#auMode").onchange = () => { const m = $("#auMode").value; $("#auMineWrap").hidden = m !== "mine"; $("#auPresetWrap").hidden = m !== "preset"; };
  planAura();
}
function paintLocs() {
  $("#auLocs").innerHTML = AURA.locations.map(l => { const i = auLocs.indexOf(l.id);
    return `<span class="chip${i >= 0 ? " on" : ""}" data-loc="${l.id}">${i >= 0 ? `<b>${i + 1}</b>` : ""}${esc(l.label)}</span>`; }).join("");
}
$("#auLocs").onclick = e => { const c = e.target.closest("[data-loc]"); if (!c) return; const id = c.dataset.loc, i = auLocs.indexOf(id);
  if (i >= 0) { if (auLocs.length > 1) auLocs.splice(i, 1); } else auLocs.push(id); paintLocs(); };
const auraOpts = () => ({ animal: $("#auAnimal").value, outfit: $("#auOutfit").value, name: $("#auName").value.trim() || undefined,
  hearts: +$("#auHearts").value, locations: auLocs, dialogue_mode: $("#auMode").value, preset: $("#auPreset").value, dialogue: $("#auLines").value });
async function planAura() {
  let p; try { p = await api("/api/aura/plan", { method: "POST", body: auraOpts() }); } catch (e) { $("#auPlan").innerHTML = `<div class="plan-sum plan-warn">⚠ ${esc(e.message)}</div>`; return; }
  $("#auPlan").innerHTML = `<div class="plan-sum"><b>${esc(p.character.name)}</b> · ${p.shots.length} shots · ~${Math.round(p.total_seconds)}s · ${p.bpm} BPM cuts · CTA: <b>${esc(p.cta)}</b>${p.warning ? ` <span class="plan-warn">⚠ ${esc(p.warning)}</span>` : ""}</div>` +
    p.shots.map(s => `<div class="shot"><div class="sh-h"><span>Shot ${s.n} · ${s.duration.toFixed(1)}s</span><span>${s.effect === "slowmo" ? "slow-mo" : s.effect}${s.lipsync ? " · lip-sync" : ""}</span></div>
      <div class="sh-l">📍 ${esc(s.location_label)}</div><q>“${esc(s.line.roman)}”</q><small>🎬 ${esc(s.action)} · ${esc(s.camera)}</small></div>`).join("");
}
$("#auPlanBtn").onclick = planAura;
["#auAnimal", "#auOutfit", "#auHearts", "#auPreset"].forEach(s => $(s).addEventListener("change", planAura));
$("#auGo").onclick = () => startJob({ template: "animal_aura", aura: auraOpts() }, "Aura reel ban rahi hai… 🦁");
paintSteps([], false);

// ---------- full control ----------
const FCSTEPS = ["YouTube khula", "Aapne login kiya", "Control AI ko diya", "YouTube Studio khula", "Saari videos analyse", "Topic list bani", "Videos ban rahi hain", "Session deleted ✅"];
let fcTimer;
function paintFc(st) {
  const n = st.stepIndex ?? -1;
  $("#fcSteps").innerHTML = FCSTEPS.map((l,i) => `<li class="${i <= n ? "done" : i === n+1 && st.active ? "now" : ""}">${l}</li>`).join("");
  $("#fcLog").innerHTML = (st.log||[]).map(e => `<div><span>${e.t}</span>${esc(e.msg)}</div>`).join(""); $("#fcLog").scrollTop = 1e9;
  $("#fcTopics").innerHTML = (st.topics||[]).map(t => `<span class="chip">${esc(t.keyword || t)}</span>`).join("") || `<span class="note">Analyse ke baad yahan topics aayenge</span>`;
  if (st.url) $("#fcUrl").textContent = st.url;
  $("#fcStop").disabled = !st.active; $("#fcShare").disabled = !(DESKTOP && st.active && !st.shared); $("#fcStart").disabled = !(DESKTOP || DEMO) || st.active;
}
function fcInit() {
  $("#fcNote").textContent = DESKTOP
    ? "Login sirf aap karte ho, Google ke apne page pe. Password app kabhi save/read nahi karta. Session khatam hote hi cookies + storage apne aap delete."
    : DEMO ? "Demo: Start dabao — simulation dikhata hai ki PC app me AI kaise kaam karta hai (asli login/edits nahi)."
    : "📱 Full Control aapke PC app pe chalta hai — yahan se live dekho aur Stop daba sakte ho.";
  clearInterval(fcTimer);
  const tick = async () => {
    const st = DESKTOP ? await window.sc.fullControl.state() : await api("/api/fc/state");
    paintFc(st);
    if (!DESKTOP && !DEMO && st.active) { $("#fcFrame").src = "/api/fc/frame?t=" + Date.now(); $("#fcEmpty").hidden = true; }
    if (DESKTOP) $("#fcEmpty").hidden = st.active;
  };
  tick(); fcTimer = setInterval(tick, 1000);
}
$("#fcStart").onclick = () => DEMO ? window.SC_FC_SIM.start() : window.sc?.fullControl.start($("#fcView").getBoundingClientRect().toJSON());
$("#fcShare").onclick = () => window.sc?.fullControl.share();
$("#fcStop").onclick = () => DESKTOP ? window.sc.fullControl.stop() : api("/api/fc/stop", {method:"POST"});
addEventListener("resize", () => DESKTOP && window.sc.fullControl.bounds($("#fcView").getBoundingClientRect().toJSON()));

// ---------- settings (every option lives only here) ----------
let SETTINGS = {};
const sel = (k, label, opts) => `<div class="f"><label>${label}</label><select data-k="${k}">${opts.map(([v,l]) => `<option value="${v}" ${SETTINGS[k]==v?"selected":""}>${l}</option>`).join("")}</select></div>`;
const txt = (k, label, full) => `<div class="f ${full?"full":""}"><label>${label}</label><input data-k="${k}" value="${esc(SETTINGS[k])}"></div>`;
const sw = (k, label) => `<label class="sw f"><span>${label}</span><input type="checkbox" data-k="${k}" ${SETTINGS[k]?"checked":""}><i></i></label>`;
async function loadSettings() {
  const [keys, s, st] = await Promise.all([api("/api/keys"), api("/api/settings"), api("/api/status")]); SETTINGS = s;
  let g = ""; $("#keys").innerHTML = keys.map(k => { const h = k.group !== g ? `<div class="grp">${k.group}</div>` : ""; g = k.group;
    return h + `<div class="key ${k.set?"set":""}"><label>${esc(k.label)}</label><a href="${k.url}" target="_blank" rel="noopener">Key kahan se ↗</a><small>${esc(k.why)}</small>
      <input type="password" data-key="${k.name}" placeholder="${k.set ? "Saved (" + esc(k.preview) + ") — badalne ke liye naya daalo" : k.name}"></div>`; }).join("");
  $("#prefContent").innerHTML = txt("niche","Niche / topics",true) + txt("channel_to_scan","Mera channel (scan)") + sel("region","Region",[["IN","India"],["US","USA"],["GB","UK"]])
    + sel("voice","Voice",[["hi-IN-SwaraNeural","Swara (female, free)"],["hi-IN-MadhurNeural","Madhur (male, free)"]]) + sel("voice_engine","Voice engine",[["edge","Edge TTS (free)"],["elevenlabs","ElevenLabs"]])
    + sel("video_style","Video style",[["photo","Photo / real"],["cartoon","Cartoon"],["3d","3D"],["stock","Sirf stock clips"]]) + sw("use_ai_video","AI video (sab providers, best upload)") + txt("end_card","End card");
  $("#prefPost").innerHTML = sw("post_youtube","YouTube Shorts") + sw("post_instagram","Instagram Reels") + sw("post_pinterest","Pinterest (apni video)")
    + sel("privacy","Upload privacy",[["private","Private (check karke public)"],["unlisted","Unlisted"],["public","Public"]])
    + sw("scheduler_on","Roz auto-run") + `<div class="f"><label>Time</label><input type="time" data-k="daily_time" value="${s.daily_time}"></div>`
    + `<div class="f full"><button class="btn" id="ytConnect">${st.youtube_connected ? "✓ YouTube connected — reconnect" : "🔐 Connect YouTube (Google sign-in)"}</button></div>`;
  $("#prefFc").innerHTML = sw("fc_update_metadata","Purani videos ke title/description/tags bhi sudhare") + sel("fc_videos_per_session","Topic list se kitni videos",[[1,"1"],[2,"2"],[3,"3"],[5,"5"]]);
  $("#phoneBox").innerHTML = st.phone.pin ? `<p class="sub">Same Wi-Fi pe phone browser me kholo:</p><div class="big">${esc(st.phone.url)}</div><p class="sub">PIN <b class="big" style="color:var(--a1)">${st.phone.pin}</b> · "Add to Home screen" se app ban jayega</p>` : `<p class="sub">PIN sirf PC pe dikhta hai.</p>`;
  $("#ytConnect").onclick = async () => { toast("Google sign-in browser me khul raha hai…"); try { await api("/api/youtube/connect", {method:"POST"}); toast("YouTube connected ✓"); loadSettings(); } catch(e) { toast(e.message); } };
}
$("#saveAll").onclick = async () => {
  const body = {}; $$("[data-k]").forEach(el => body[el.dataset.k] = el.type === "checkbox" ? el.checked : (el.dataset.k === "fc_videos_per_session" ? +el.value : el.value));
  const keys = {}; $$("[data-key]").forEach(el => { if (el.value.trim()) keys[el.dataset.key] = el.value.trim(); });
  await api("/api/settings", {method:"POST", body}); if (Object.keys(keys).length) await api("/api/keys", {method:"POST", body: keys});
  toast("Saved ✓"); loadSettings();
};

// ---------- AI chat (acts only on the app's own features) ----------
const msgs = $("#msgs");
const say = (cls, t) => { msgs.insertAdjacentHTML("beforeend", `<div class="m ${cls}">${esc(t)}</div>`); msgs.scrollTop = 1e9; };
say("ai", "Namaste! Main app ke andar sab kar sakta hoon: trend dhundna, channel scan, video banana, settings badalna. Bolo kya karu? 🙂");
$("#chatForm").onsubmit = async e => {
  e.preventDefault(); const q = $("#chatIn").value.trim(); if (!q) return; $("#chatIn").value = ""; say("me", q);
  try {
    const r = await api("/api/chat", { method: "POST", body: { message: q } });
    say("ai", r.reply); (r.done || []).forEach(a => say("act", "✓ " + a));
    if (r.goto) location.hash = "#" + r.goto;
    if (r.template) setTemplate(r.template);
    if (r.job) { $("#topic").value = r.topic || ""; location.hash = "#create"; }
  } catch (err) { say("ai", "Error: " + err.message); }
};
const openChat = () => { $("#chat").classList.add("open"); document.body.classList.add("chat-open"); $("#chatFab").classList.remove("badge"); };
$("#chatFab").onclick = openChat;
$("#chatClose").onclick = () => { $("#chat").classList.remove("open"); document.body.classList.remove("chat-open"); };

// ---------- permission cards (Accept / Cancel) ----------
const shownCards = new Set();
const KIND = { create: "🎬 Video", post: "📤 Post", settings: "⚙ Settings", fullcontrol: "⌘ Full Control", edit: "✏️ Edit" };
async function pollApprovals() {
  try {
    const list = await api("/api/approvals");
    for (const a of list) {
      if (shownCards.has(a.id)) continue; shownCards.add(a.id);
      msgs.insertAdjacentHTML("beforeend", `<div class="perm" id="ap-${a.id}"><div class="perm-h"><span>${KIND[a.kind] || a.kind} · permission</span><small>${esc(a.created)}</small></div>
        <b>${esc(a.title)}</b><ul>${a.details.map(d => `<li>${esc(d)}</li>`).join("")}</ul>
        <div class="perm-b"><button class="btn sm ok" data-ap="${a.id}" data-acc="1">✅ Accept</button><button class="btn sm" data-ap="${a.id}" data-acc="0">❌ Cancel</button></div></div>`);
      msgs.scrollTop = 1e9; $("#chatFab").classList.add("badge");
    }
  } catch (e) {}
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-ap]"); if (!b) return;
  const acc = b.dataset.acc === "1"; const r = await api("/api/approvals/" + b.dataset.ap, { method: "POST", body: { accept: acc } });
  const card = $("#ap-" + b.dataset.ap); card.querySelector(".perm-b").innerHTML = acc ? `<span class="done-ok">✅ Accepted — kaam shuru</span>` : `<span class="done-no">❌ Cancelled — kuch nahi badla</span>`;
  card.classList.add(acc ? "accepted" : "cancelled");
});
setInterval(pollApprovals, 1500); pollApprovals();

// ---------- pin gate (phone) ----------
$("#pinGo").onclick = async () => { await fetch("/api/login", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({pin: $("#pinIn").value})}).then(r => { if (r.ok) location.reload(); else toast("Galat PIN"); }); };

if ("serviceWorker" in navigator && !DESKTOP && !DEMO) navigator.serviceWorker.register("sw.js").catch(() => {});
route();
if (DEMO && new URLSearchParams(location.search).has('fcauto')) setTimeout(() => window.SC_FC_SIM.start(), 300);
if (DEMO && new URLSearchParams(location.search).has('chatopen')) openChat();
if (DEMO && new URLSearchParams(location.search).has('chatdemo')) { say('me','Instagram pe abhi post mat karo'); say('ai','Theek hai 👍 pehle permission card dekh lo.'); }
if (DEMO && new URLSearchParams(location.search).has('autocreate')) setTimeout(create, 200);
if (new URLSearchParams(location.search).has("aura")) { location.hash = "#create"; setTemplate("animal_aura"); }
