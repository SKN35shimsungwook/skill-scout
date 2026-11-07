// skill-scout 화면: 메뉴 전환 · 상담 채팅 · 사무실(아침 점검) · 내 도구
const $ = s => document.querySelector(s);
const CHAT_NEXT = { consultant: "collector", collector: "inspector", inspector: "verifier", verifier: "consultant" };
const TIER_TAG = { "필수": "bad", "추천": "info" };
let busy = false;

function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2400); }
function copy(text, msg) { navigator.clipboard.writeText(text).then(() => toast(msg)); }

// ---------- 메뉴 ----------
function go(view) {
  document.querySelectorAll(".nav").forEach(n => n.classList.toggle("on", n.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("on", v.id === `view-${view}`));
  if (view === "tools") loadTools();
}
document.querySelectorAll(".nav").forEach(n => n.onclick = () => go(n.dataset.view));
document.querySelectorAll("[data-goto]").forEach(b => b.onclick = () => go(b.dataset.goto));

fetch("/api/status").then(r => r.json()).then(s => {
  $("#dotGemini").className = "dot " + (s.gemini ? "on" : "off");
  $("#txtGemini").textContent = s.gemini ? `상담팀: Gemini (${s.model})` : "상담팀: 단어 매칭 (Gemini 키 없음)";
  $("#dotDiscord").className = "dot " + (s.discord ? "on" : "off");
  $("#txtDiscord").textContent = s.discord ? "디스코드 연결됨" : "디스코드 미연결";
});

// ---------- 부서 진행 상황 (상담 화면 오른쪽) ----------
const deptRows = {};
for (const [key, d] of Object.entries(DEPT)) {
  const row = h("div", "dept"); const face = h("div", "face", d.name[0]); face.style.background = d.color;
  const body = h("div"); body.append(h("b", null, d.name), h("p", null, "대기 중"));
  row.append(face, body); $("#deptList").append(row); deptRows[key] = row;
}
function railUpdate(ev) {
  const row = deptRows[ev.dept]; if (!row) return;
  const state = { start: "work", work: "work", done: "done", retry: "retry" }[ev.status];
  if (state) { row.className = "dept " + state; row.querySelector("p").textContent = ev.msg; }
}
function railReset() { Object.values(deptRows).forEach(r => { r.className = "dept"; r.querySelector("p").textContent = "대기 중"; }); }

// ---------- 사무실 ----------
Office.init($("#office"));
function log(ev) {
  if (!DEPT[ev.dept] || ["end", "result"].includes(ev.status)) return;
  const li = h("li", ev.status); const who = h("span", "who", DEPT[ev.dept].name); who.style.color = DEPT[ev.dept].color;
  li.append(who, h("span", null, ev.msg)); $("#timeline").append(li); $("#timeline").scrollTop = 1e9;
}
function resetAll() { Office.reset(); railReset(); $("#timeline").innerHTML = ""; }
function setBusy(on, label) { busy = on; $("#runBtn").disabled = $("#replayBtn").disabled = $("#sendBtn").disabled = on; $("#officeStatus").textContent = label || (on ? "진행 중" : "완료"); }

// 추천 카드 (사무실·채팅 공용)
function recCard(p, i) {
  const g = p.guide || { summary: "", cases: [], example: "", caveat: "", tier: "확인 후", steps: [] };
  const c = h("div", "rec");
  const title = h("h3"); title.append(h("span", null, (i != null ? `${i + 1}. ` : "") + p.name), h("span", "tag " + (TIER_TAG[g.tier] || ""), g.tier), h("span", "tag", p.kind));
  if (p.official) title.append(h("span", "tag accent", "공식"));
  if (p.verdict) title.append(h("span", "tag " + (p.verdict === "PASS" ? "ok" : "warn"), p.verdict === "PASS" ? "검증 통과" : "확인 필요"));
  c.append(title, h("p", "sum", g.summary));
  if (g.cases.length) { c.append(h("h5", null, "이럴 때 쓰세요")); const ul = h("ul"); g.cases.forEach(t => ul.append(h("li", null, t))); c.append(ul); }
  if (g.example) {
    c.append(h("h5", null, "이렇게 말하면 돼요")); const say = h("div", "say"); say.append(h("span", null, g.example));
    if (!g.example.startsWith("(")) { const b = h("button", "btn ghost sm", "복사"); b.onclick = () => copy(g.example, "복사했어요. 설치 후 Claude에게 그대로 말해 보세요"); say.append(b); }
    c.append(say);
  }
  if (p.install) {
    c.append(h("h5", null, "설치 순서")); const ol = h("ol"); g.steps.forEach(t => ol.append(h("li", null, t))); c.append(ol, h("code", null, p.install));
    const acts = h("div", "acts"); const cp = h("button", "btn primary sm", "설치 명령 복사"); cp.onclick = () => copy(p.install, "복사했어요. 터미널에 붙여 넣어 설치하세요"); acts.append(cp);
    if (p.url) { const op = h("button", "btn line sm", "자세히 보기"); op.onclick = () => window.open(p.url, "_blank", "noopener"); acts.append(op); }
    c.append(acts);
  }
  if (g.caveat) c.append(h("p", "caveat", "⚠️ " + g.caveat));
  const det = h("details"); det.append(h("summary", null, "추천 근거 · 원문 설명"));
  [p.reason, p.verdict_note && "검증: " + p.verdict_note, p.description].filter(Boolean).forEach(t => det.append(h("p", null, t)));
  c.append(det);
  return c;
}
function renderMorning(data) {
  $("#summary").textContent = "💬 " + data.summary;
  $("#cards").innerHTML = ""; data.picks.forEach((p, i) => $("#cards").append(recCard(p, i)));
}
function morningEvent(ev) {
  Office.handle(ev); railUpdate(ev); log(ev);
  if (ev.status === "start") $("#officeStatus").textContent = `${DEPT[ev.dept].name} 일하는 중`;
  if (ev.status === "result" && ev.data && ev.data.picks) renderMorning(ev.data);
  if (["sent", "not_sent", "error", "busy"].includes(ev.status)) toast(ev.msg);
}
$("#runBtn").onclick = () => {
  if (busy) return; resetAll(); setBusy(true);
  const es = new EventSource(`/run?send=${$("#sendChk").checked ? 1 : 0}`);
  es.onmessage = m => { const ev = JSON.parse(m.data); morningEvent(ev); if (["end", "busy"].includes(ev.status)) { es.close(); setBusy(false); } };
  es.onerror = () => { es.close(); setBusy(false, "연결 끊김"); };
};
$("#replayBtn").onclick = async () => {
  if (busy) return;
  const evs = await (await fetch("/replay")).json();
  if (!evs.length) return toast("아직 저장된 점검이 없어요. '아침 점검 지금 실행'을 먼저 눌러 주세요");
  resetAll(); setBusy(true, "다시 보는 중");
  for (const ev of evs) { morningEvent(ev); if (["start", "work", "done", "handoff", "retry"].includes(ev.status)) await new Promise(r => setTimeout(r, 400)); }
  setBusy(false);
};
fetch("/replay").then(r => r.json()).then(evs => { const r = evs.find(e => e.status === "result" && e.data && e.data.picks); if (r) renderMorning(r.data); });

// ---------- 상담 채팅 ----------
const input = $("#chatInput");
input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; });
input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#chatForm").requestSubmit(); } });
document.querySelectorAll(".suggest button").forEach(b => b.onclick = () => ask(b.textContent));
$("#chatForm").onsubmit = e => { e.preventDefault(); const q = input.value.trim(); if (q) ask(q); };

function ask(q) {
  if (busy) return toast("부서들이 아직 일하는 중이에요");
  $("#hello")?.remove(); input.value = ""; input.style.height = "auto";
  const box = $("#messages");
  box.append(h("div", "msg me", q));
  const bot = h("div", "msg bot");
  const who = h("div", "who"); who.append(h("span", "av", "상"), h("span", null, "상담팀"));
  const working = h("div", "working"); const step = h("span", null, "질문을 접수하는 중…"); working.append(h("span", "spin"), step);
  bot.append(who, working); box.append(bot); box.scrollTop = 1e9;
  const trace = [];
  resetAll(); setBusy(true, "상담 처리 중");
  const es = new EventSource(`/chat?q=${encodeURIComponent(q)}`);
  es.onmessage = m => {
    const ev = JSON.parse(m.data);
    Office.handle(ev, CHAT_NEXT); railUpdate(ev); log(ev);
    if (DEPT[ev.dept] && ["start", "work", "done", "retry"].includes(ev.status)) { step.textContent = `${DEPT[ev.dept].name}: ${ev.msg}`; trace.push(`${DEPT[ev.dept].name} — ${ev.msg}`); }
    if (ev.status === "result" && ev.data && ev.data.mode === "chat") renderAnswer(bot, working, ev.data, trace);
    if (ev.status === "error") { working.replaceChildren(h("span", null, "⚠️ " + ev.msg)); }
    if (ev.status === "end") { es.close(); setBusy(false); }
    box.scrollTop = 1e9;
  };
  es.onerror = () => { es.close(); setBusy(false, "연결 끊김"); working.replaceChildren(h("span", null, "⚠️ 서버 연결이 끊겼어요")); };
}

function renderAnswer(bot, working, d, trace) {
  working.remove();
  bot.querySelector(".who").append(h("span", "tag", d.engine === "Gemini" ? "Gemini" : "단어 매칭"), ...(d.task ? [h("span", "tag accent", d.task)] : []));
  bot.append(h("p", "answer", d.answer));
  if (d.have.length) {
    const g = h("div", "group"); g.append(h("h4", null, "✅ 이미 있어요 — 바로 쓰면 돼요"));
    d.have.forEach(t => {
      const row = h("div", "row"); const body = h("div");
      body.append(h("b", null, t.name), h("p", null, `${t.kind} · ${t.where || "설치됨"}`));
      const ex = `${t.name} 써서 ${(d.task || "이 작업").split(" · ")[0]} 도와줘`;
      body.append(h("div", "say", "💬 " + ex));
      const cp = h("button", "btn line sm", "문장 복사"); cp.onclick = () => copy(ex, "복사했어요. Claude에게 그대로 말해 보세요");
      row.append(body, cp); g.append(row);
    });
    bot.append(g);
  }
  if (d.install.length) { const g = h("div", "group"); g.append(h("h4", null, "📦 설치 추천")); const cards = h("div", "cards"); d.install.forEach(p => cards.append(recCard(p))); g.append(cards); bot.append(g); }
  if (d.optional.length) { const g = h("div", "group"); g.append(h("h4", null, "💡 선택 — 필요하면 살펴보세요")); const cards = h("div", "cards"); d.optional.forEach(p => cards.append(recCard(p))); g.append(cards); bot.append(g); }
  const det = h("details", "trace"); det.append(h("summary", null, `부서 처리 과정 보기 (${trace.length}단계)`));
  const ol = h("ol"); trace.forEach(t => ol.append(h("li", null, t))); det.append(ol); bot.append(det);
}

// ---------- 내 도구 ----------
async function loadTools() {
  const tools = await (await fetch("/api/installed")).json();
  const plugins = tools.filter(t => t.kind === "플러그인").length;
  $("#toolCount").textContent = `스킬 ${tools.length - plugins}개 · 플러그인 ${plugins}개. 아침 추천에서는 빠지고, 상담에서는 '이미 있어요'로 알려 드려요.`;
  $("#toolList").innerHTML = "";
  tools.forEach(t => { const d = h("div", "t"); d.append(h("b", null, t.name), h("small", null, `${t.kind} · ${t.where}`)); if (t.description) d.append(h("p", null, t.description)); $("#toolList").append(d); });
}
