// 2D 픽셀 사무실: 부서 이벤트를 받아 캐릭터·말풍선·서류를 움직인다.
const DEPT = {
  collector:  { name: "수집기", color: "#8B5CF6", hair: "#6b21a8", chars: [[845, 212]], bubble: [845, 288], hub: [800, 240], plate: [714, 104] },
  inspector:  { name: "점검팀", color: "#F59E0B", hair: "#7c2d12", chars: [[100, 250], [260, 250]], bubble: [230, 164], hub: [300, 230], plate: [36, 104] },
  verifier:   { name: "검증팀", color: "#10B981", hair: "#14532d", chars: [[790, 450]], bubble: [840, 330], hub: [740, 420], plate: [714, 340] },
  briefer:    { name: "브리핑팀", color: "#EF4444", hair: "#7f1d1d", chars: [[260, 470]], bubble: [190, 600], hub: [300, 540], plate: [36, 436] },
  consultant: { name: "상담팀", color: "#4F7CFF", hair: "#111827", chars: [[520, 150]], bubble: [520, 300], hub: [520, 230], plate: [580, 150] },
};
const NEXT = { collector: "inspector", inspector: "verifier", verifier: "briefer", briefer: "consultant", consultant: "collector" };

const Office = (() => {
  const NS = "http://www.w3.org/2000/svg";
  let svg, racks = [], inspScreens = [], checks = [], envelope, doc, verdictIdx = 0;
  const parts = {}, bubbles = {};

  const el = (tag, attrs = {}, parent = svg) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    parent.appendChild(e); return e;
  };
  const rect = (x, y, w, h, fill, p = svg, extra = {}) => el("rect", { x, y, width: w, height: h, fill, ...extra }, p);
  const text = (x, y, t, size, fill, p = svg, extra = {}) => {
    const e = el("text", { x, y, "font-size": size, fill, "font-weight": 800, "text-anchor": "middle", ...extra }, p);
    e.textContent = t; return e;
  };
  function person(x, y, shirt, hair) {
    const g = el("g");
    el("ellipse", { cx: x, cy: y + 44, rx: 15, ry: 5, fill: "rgba(0,0,0,.25)" }, g);
    rect(x - 12, y + 18, 24, 22, shirt, g, { stroke: "#1f2937", "stroke-width": 2 });
    rect(x - 10, y, 20, 18, "#F6C9A0", g, { stroke: "#1f2937", "stroke-width": 2 });
    rect(x - 11, y - 3, 22, 8, hair, g, { stroke: "#1f2937", "stroke-width": 2 });
    rect(x - 5, y + 9, 3, 3, "#1f2937", g); rect(x + 2, y + 9, 3, 3, "#1f2937", g);
    return g;
  }
  function desk(x, y, w, screen) {
    rect(x, y, w, 50, "#B07A4A", svg, { stroke: "#5b3a1e", "stroke-width": 2.5 });
    rect(x + w / 2 - 26, y + 6, 52, 32, "#1f2937");
    return rect(x + w / 2 - 22, y + 10, 44, 24, screen);
  }
  const wall = (x1, y1, x2, y2) => el("line", { x1, y1, x2, y2, stroke: "#3f3a34", "stroke-width": 10 });

  function draw() {
    rect(0, 0, 1000, 620, "#D99A5B");
    for (let i = 0; i < 620; i += 26) el("line", { x1: 0, y1: i, x2: 1000, y2: i, stroke: "#c4834a", "stroke-width": 2 });
    rect(0, 0, 1000, 86, "#EDE7DC"); rect(0, 82, 1000, 6, "#b9ad9a");
    rect(20, 12, 86, 60, "#7dd3fc", svg, { stroke: "#1f2937", "stroke-width": 3 });
    el("circle", { cx: 150, cy: 42, r: 20, fill: "#fff", stroke: "#1f2937", "stroke-width": 3 });
    el("line", { x1: 150, y1: 42, x2: 150, y2: 28, stroke: "#1f2937", "stroke-width": 3 });
    el("line", { x1: 150, y1: 42, x2: 160, y2: 48, stroke: "#1f2937", "stroke-width": 3 });
    rect(200, 12, 200, 60, "#fff", svg, { stroke: "#6b7280", "stroke-width": 3 });
    text(300, 38, "skill-scout 사무실", 15, "#ef4444"); text(300, 60, "상담 · 아침 점검", 13, "#374151");
    // 서버실 (수집기)
    rect(700, 0, 300, 300, "#e5e7eb"); rect(700, 0, 300, 86, "#d6dde8");
    wall(700, 0, 700, 250); wall(700, 300, 760, 300); wall(830, 300, 1000, 300);
    ["공식 마켓", "Anthropic", "skills.sh", "내 도구"].forEach((n, i) => {
      const x = 716 + i * 70;
      rect(x, 110, 56, 90, "#1f2937", svg, { stroke: "#000", "stroke-width": 3 });
      for (let k = 0; k < 4; k++) { rect(x + 6, 118 + k * 20, 44, 12, "#374151"); racks.push(el("circle", { cx: x + 44, cy: 124 + k * 20, r: 3, fill: "#4b5563" })); }
      rect(x - 4, 204, 64, 20, DEPT.collector.color, svg, { rx: 4 }); text(x + 28, 219, n, 11, "#fff");
    });
    inspScreens = [desk(40, 180, 120, "#7dd3fc"), desk(200, 180, 120, "#7dd3fc")];
    // 상담팀 안내 데스크
    rect(440, 196, 160, 44, "rgba(191,219,254,.8)", svg, { stroke: "#64748b", "stroke-width": 3, rx: 4 });
    person(470, 250, "#64748b", "#57534e"); text(470, 312, "나", 12, "#1f2937");
    // 검증팀
    desk(730, 380, 120, "#bbf7d0");
    rect(880, 372, 70, 90, "#fef3c7", svg, { stroke: "#1f2937", "stroke-width": 2.5, rx: 4 });
    checks = [0, 1, 2].map(k => { const t = text(898, 400 + k * 22, "·", 16, "#9ca3af"); rect(910, 393 + k * 22, 30, 4, "#9ca3af"); return t; });
    // 브리핑팀 회의실
    rect(0, 420, 380, 200, "#9fb2d4");
    wall(0, 420, 250, 420); wall(330, 420, 380, 420); wall(380, 420, 380, 620);
    rect(50, 520, 200, 56, "#7c4a24", svg, { stroke: "#3b2414", "stroke-width": 3, rx: 6 });
    envelope = rect(170, 530, 50, 32, "#fff", svg, { stroke: "#1f2937", "stroke-width": 2.5 });
    el("polyline", { points: "170,530 195,548 220,530", fill: "none", stroke: "#1f2937", "stroke-width": 2.5 });
    // 라운지
    rect(600, 470, 400, 150, "#E9D6B0");
    rect(900, 490, 80, 110, "#8b5a2b", svg, { stroke: "#3b2414", "stroke-width": 3 });
    for (let r = 0; r < 4; r++) for (let c = 0; c < 5; c++) rect(906 + c * 14, 496 + r * 26, 11, 20, ["#0ea5e9", "#a855f7", "#f97316", "#22c55e"][(r + c) % 4]);
    text(940, 612, "스킬 서가", 11, "#1f2937");
    rect(640, 520, 150, 40, "#7e3aa8", svg, { stroke: "#3b0764", "stroke-width": 3, rx: 8 });
    rect(0, 0, 1000, 620, "none", svg, { stroke: "#2a2520", "stroke-width": 10 });
    // 부서별 캐릭터·명패·상태등
    for (const [key, d] of Object.entries(DEPT)) {
      const chars = d.chars.map(([x, y]) => person(x, y, d.color, d.hair));
      const [px, py] = d.plate, w = d.name.length * 15 + 44;
      rect(px, py, w, 28, d.color, svg, { stroke: "#1f2937", "stroke-width": 2, rx: 6 });
      const lamp = el("circle", { cx: px + 15, cy: py + 14, r: 7, fill: "#9ca3af", stroke: "#fff", "stroke-width": 2 });
      text(px + 28, py + 19, d.name, 14, "#fff", svg, { "text-anchor": "start" });
      parts[key] = { chars, lamp };
    }
    for (const [key, d] of Object.entries(DEPT)) {
      const g = el("g", { visibility: "hidden" });
      bubbles[key] = { g, box: rect(0, 0, 10, 30, "#fff", g, { stroke: d.color, "stroke-width": 2.5, rx: 8 }), t: text(0, 0, "", 13, "#1f2937", g) };
    }
    doc = rect(-50, -50, 18, 22, "#fff", svg, { stroke: "#1f2937", "stroke-width": 2 });
  }

  function say(key, msg, color) {
    const b = bubbles[key], [x, y] = DEPT[key].bubble;
    b.t.textContent = msg.length > 30 ? msg.slice(0, 29) + "…" : msg;
    const w = b.t.getComputedTextLength() + 24;
    Object.entries({ x: x - w / 2, y: y - 21, width: w, stroke: color || DEPT[key].color }).forEach(([k, v]) => b.box.setAttribute(k, v));
    b.t.setAttribute("x", x); b.t.setAttribute("y", y);
    b.g.setAttribute("visibility", "visible");
  }
  function setState(key, state) {
    const d = parts[key];
    d.chars.forEach(c => c.classList.toggle("bob", state === "work"));
    d.lamp.setAttribute("fill", { idle: "#9ca3af", work: "#fbbf24", done: "#22c55e", retry: "#ef4444" }[state]);
    if (key === "collector") racks.forEach((r, i) => r.setAttribute("fill", state === "work" ? (i % 3 ? "#22c55e" : "#facc15") : "#4b5563"));
    if (key === "inspector") inspScreens.forEach(s => s.setAttribute("fill", state === "work" ? "#fde68a" : "#7dd3fc"));
  }
  function fly(from, to, color) {
    const [x1, y1] = DEPT[from].hub, [x2, y2] = DEPT[to].hub, t0 = performance.now();
    doc.setAttribute("stroke", color);
    (function step(now) {
      const k = Math.min(1, (now - t0) / 550);
      doc.setAttribute("x", x1 + (x2 - x1) * k - 9); doc.setAttribute("y", y1 + (y2 - y1) * k - 11 - Math.sin(k * Math.PI) * 40);
      if (k < 1) requestAnimationFrame(step); else doc.setAttribute("x", -50);
    })(t0);
  }

  return {
    init(svgEl) { svg = svgEl; draw(); Object.keys(DEPT).forEach(k => setState(k, "idle")); },
    reset() {
      verdictIdx = 0;
      Object.keys(DEPT).forEach(k => { setState(k, "idle"); bubbles[k].g.setAttribute("visibility", "hidden"); });
      checks.forEach(c => { c.textContent = "·"; c.setAttribute("fill", "#9ca3af"); });
      envelope.setAttribute("fill", "#fff");
    },
    // handoff의 다음 부서: 채팅에서는 검증팀 → 상담팀, 상담팀 → 수집기
    handle(ev, nextOf = NEXT) {
      const k = ev.dept;
      if (!DEPT[k]) return;
      switch (ev.status) {
        case "start": case "work": setState(k, "work"); say(k, ev.msg);
          if (k === "verifier" && ev.data && ev.data.verdict) {
            const c = checks[verdictIdx++ % 3];
            c.textContent = { PASS: "✓", WARNING: "!", FAIL: "✕" }[ev.data.verdict];
            c.setAttribute("fill", { PASS: "#16a34a", WARNING: "#d97706", FAIL: "#dc2626" }[ev.data.verdict]);
          }
          break;
        case "done": setState(k, "done"); say(k, ev.msg); break;
        case "handoff": if (nextOf[k]) fly(k, nextOf[k], DEPT[k].color); break;
        case "retry":
          setState(k, "retry"); say(k, ev.msg, "#ef4444"); fly("verifier", "inspector", "#ef4444");
          parts.verifier.lamp.classList.remove("flash"); void parts.verifier.lamp.getBBox(); parts.verifier.lamp.classList.add("flash");
          break;
        case "sent": case "not_sent": envelope.setAttribute("fill", ev.status === "sent" ? "#bbf7d0" : "#fff"); break;
      }
    },
  };
})();
