/* django-strava · chart renderers (vanilla SVG/canvas, accent-aware) */
window.DSCharts = (function () {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /* ---- Hero route trace ---- */
  function renderRoute(svg, pts) {
    svg.innerHTML = "";
    svg.setAttribute("viewBox", "0 0 100 96");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const sx = 84 / (maxX - minX), sy = 76 / (maxY - minY);
    const s = Math.min(sx, sy);
    const ox = (100 - (maxX - minX) * s) / 2 - minX * s;
    const oy = (96 - (maxY - minY) * s) / 2 - minY * s;
    const P = pts.map(p => [(p[0] * s + ox).toFixed(2), (p[1] * s + oy).toFixed(2)]);
    const dAttr = "M" + P.map(p => p.join(",")).join(" L");
    const halo = el("path", { d: dAttr, fill: "none", "stroke-width": 3.6, "stroke-linecap": "round", "stroke-linejoin": "round" });
    halo.style.stroke = "var(--surface)";
    const line = el("path", { d: dAttr, fill: "none", "stroke-width": 1.7, "stroke-linecap": "round", "stroke-linejoin": "round" });
    line.style.stroke = "var(--accent)";
    svg.appendChild(halo); svg.appendChild(line);
    const start = el("circle", { cx: P[0][0], cy: P[0][1], r: 2.4 });
    start.style.fill = "var(--ink)";
    const endO = el("circle", { cx: P[P.length-1][0], cy: P[P.length-1][1], r: 2.8 });
    endO.style.fill = "var(--accent)";
    const endI = el("circle", { cx: P[P.length-1][0], cy: P[P.length-1][1], r: 1.1 });
    endI.style.fill = "var(--surface)";
    svg.appendChild(start); svg.appendChild(endO); svg.appendChild(endI);
  }

  /* ---- Elevation profile (small area chart) ---- */
  function renderProfile(svg, heights) {
    svg.innerHTML = "";
    const W = 100, H = 30;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("preserveAspectRatio", "none");
    const min = Math.min(...heights), max = Math.max(...heights);
    const pt = (i, h) => [
      (i / (heights.length - 1) * W).toFixed(2),
      (H - 3 - (h - min) / (max - min) * (H - 8)).toFixed(2),
    ];
    const pl = heights.map((h, i) => pt(i, h).join(",")).join(" ");
    const area = el("polygon", { points: `0,${H} ${pl} ${W},${H}` });
    area.style.fill = "var(--accent-soft)";
    const line = el("polyline", { points: pl, fill: "none", "stroke-width": 1.1, "stroke-linejoin": "round" });
    line.style.stroke = "var(--accent)";
    svg.appendChild(area); svg.appendChild(line);
  }

  /* ---- Regional density blobs (canvas) ---- */
  function renderDensity(canvas, areas) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w) return;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);
    const accent = css("--accent") || "#C9501C";
    // fixed positions, radius ∝ sqrt(km)
    const pos = [[0.30, 0.62], [0.50, 0.38], [0.78, 0.22], [0.16, 0.30]];
    const maxKm = Math.max(...areas.map(a => a.km));
    areas.forEach((a, i) => {
      const [px, py] = pos[i];
      const R = 18 + 56 * Math.sqrt(a.km / maxKm);
      const g = ctx.createRadialGradient(px * w, py * h, 2, px * w, py * h, R);
      g.addColorStop(0, accent + "B8");
      g.addColorStop(0.45, accent + "55");
      g.addColorStop(1, accent + "00");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(px * w, py * h, R, 0, 7); ctx.fill();
    });
    areas.forEach((a, i) => {
      const [px, py] = pos[i];
      ctx.fillStyle = css("--ink") || "#2b2520";
      ctx.beginPath(); ctx.arc(px * w, py * h, 2.4, 0, 7); ctx.fill();
    });
  }

  /* ---- Trends bar chart with hover tooltip ---- */
  function renderTrends(host, rows, metric, tooltip) {
    host.innerHTML = "";
    const W = host.clientWidth || 760, H = host.clientHeight || 240;
    const padL = 44, padB = 26, padT = 14, padR = 8;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H });
    const unit = { km: "km", elev: "m", hours: "h", pace: "/km" }[metric];
    const fmtVal = metric === "pace"
      ? (v) => { const m = Math.floor(v); return m + ":" + String(Math.round((v - m) * 60)).padStart(2, "0"); }
      : fmtTick;
    const vals = rows.map(x => x[metric]);
    const maxV = Math.max(...vals) * 1.12;
    // y gridlines: 4 nice steps
    const step = niceStep(maxV / 4);
    for (let v = 0; v * step <= maxV; v++) {
      const yv = v * step;
      const y = H - padB - (yv / maxV) * (H - padB - padT);
      const ln = el("line", { x1: padL, y1: y, x2: W - padR, y2: y, "stroke-width": 1 });
      ln.style.stroke = v === 0 ? "var(--line)" : "var(--line-2)";
      svg.appendChild(ln);
      const t = el("text", { x: padL - 8, y: y + 3.5, "text-anchor": "end", "font-size": 10.5 });
      t.textContent = fmtVal(yv);
      t.style.fill = "var(--ink-3)"; t.style.fontFamily = "var(--font-mono)";
      svg.appendChild(t);
    }
    const n = rows.length;
    const slot = (W - padL - padR) / n;
    const bw = Math.min(34, Math.max(5, slot * 0.62));
    // x labels: thin to ~10 max
    const every = Math.ceil(n / 10);
    rows.forEach((rrow, i) => {
      const v = rrow[metric];
      const x = padL + slot * i + (slot - bw) / 2;
      const bh = (v / maxV) * (H - padB - padT);
      const y = H - padB - bh;
      const bar = el("rect", { x: x.toFixed(1), y: y.toFixed(1), width: bw.toFixed(1), height: Math.max(1.5, bh).toFixed(1), rx: Math.min(3, bw / 3) });
      bar.style.fill = rrow.partial ? "var(--accent-line)" : "var(--accent)";
      bar.style.cursor = "default";
      bar.addEventListener("mouseenter", e => {
        bar.style.fill = "var(--accent-ink)";
        tooltip.innerHTML = `<strong>${rrow.label}</strong> ${fmtVal(v)} ${unit}`;
        tooltip.style.opacity = 1;
      });
      bar.addEventListener("mousemove", e => {
        const hostRect = host.getBoundingClientRect();
        tooltip.style.left = (e.clientX - hostRect.left + 12) + "px";
        tooltip.style.top = (e.clientY - hostRect.top - 30) + "px";
      });
      bar.addEventListener("mouseleave", () => {
        bar.style.fill = rrow.partial ? "var(--accent-line)" : "var(--accent)";
        tooltip.style.opacity = 0;
      });
      svg.appendChild(bar);
      if (i % every === 0) {
        const t = el("text", { x: x + bw / 2, y: H - 8, "text-anchor": "middle", "font-size": 10.5 });
        t.textContent = rrow.label;
        t.style.fill = "var(--ink-3)"; t.style.fontFamily = "var(--font-mono)";
        svg.appendChild(t);
      }
    });
    host.appendChild(svg);
  }
  function niceStep(raw) {
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / mag;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * mag;
  }
  function fmtTick(v) {
    return v >= 10000 ? (v / 1000).toFixed(0) + "k" : Math.round(v).toLocaleString("en-US");
  }

  /* ---- Full-year heatmap calendar (GitHub-style) ---- */
  function renderCalendar(host, days, tooltip) {
    host.innerHTML = "";
    const cell = 12, gapPx = 3;
    const yearStart = new Date(2026, 0, 1);
    const lead = (yearStart.getDay() + 6) % 7; // Mon=0
    const totalWeeks = 53;
    const W = totalWeeks * (cell + gapPx) + 34;
    const H = 7 * (cell + gapPx) + 22;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%" });
    svg.style.display = "block";
    const dayMap = {};
    days.forEach(x => { dayMap[x.date.getMonth() + "-" + x.date.getDate()] = x; });
    const kms = days.map(x => x.km).filter(k => k > 0).sort((a, b) => a - b);
    const q = p => kms[Math.floor(p * (kms.length - 1))];
    const th = [q(0.25), q(0.5), q(0.75)];
    const dows = ["M", "", "W", "", "F", "", "S"];
    dows.forEach((lab, i) => {
      if (!lab) return;
      const t = el("text", { x: 0, y: 14 + i * (cell + gapPx) + cell - 3, "font-size": 9.5 });
      t.textContent = lab; t.style.fill = "var(--ink-3)"; t.style.fontFamily = "var(--font-mono)";
      svg.appendChild(t);
    });
    const mNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    let lastMonth = -1;
    const today = new Date(2026, 5, 8);
    const dd = new Date(2026, 0, 1);
    while (dd.getFullYear() === 2026) {
      const idx = Math.floor(((dd - yearStart) / 86400000 + lead) );
      const week = Math.floor(idx / 7), dow = idx % 7;
      const x = 22 + week * (cell + gapPx), y = 14 + dow * (cell + gapPx);
      if (dd.getMonth() !== lastMonth && dow <= 1) {
        lastMonth = dd.getMonth();
        const t = el("text", { x, y: 8, "font-size": 9.5 });
        t.textContent = mNames[lastMonth];
        t.style.fill = "var(--ink-3)"; t.style.fontFamily = "var(--font-mono)";
        svg.appendChild(t);
      }
      const rec = dayMap[dd.getMonth() + "-" + dd.getDate()];
      const future = dd > today;
      let lvl = 0;
      if (rec && rec.km > 0) lvl = rec.km > th[2] ? 4 : rec.km > th[1] ? 3 : rec.km > th[0] ? 2 : 1;
      const rect = el("rect", { x, y, width: cell, height: cell, rx: 3 });
      rect.style.fill = `var(--heat-0)`;
      if (!future && lvl > 0) rect.style.fill = `var(--heat-${lvl})`;
      if (future) rect.style.opacity = "0.38";
      const dateStr = mNames[dd.getMonth()] + " " + dd.getDate();
      const kmv = rec ? rec.km : 0;
      rect.addEventListener("mouseenter", () => {
        tooltip.innerHTML = future
          ? `<strong>${dateStr}</strong> —`
          : `<strong>${dateStr}</strong> ${kmv > 0 ? kmv.toFixed(1) + " km" : "rest day"}`;
        tooltip.style.opacity = 1;
      });
      rect.addEventListener("mousemove", e => {
        const hr = host.getBoundingClientRect();
        tooltip.style.left = (e.clientX - hr.left + 12) + "px";
        tooltip.style.top = (e.clientY - hr.top - 30) + "px";
      });
      rect.addEventListener("mouseleave", () => { tooltip.style.opacity = 0; });
      svg.appendChild(rect);
      dd.setDate(dd.getDate() + 1);
    }
    host.appendChild(svg);
  }

  function decodePolyline(str) {
    let idx = 0, lat = 0, lng = 0, pts = [];
    while (idx < str.length) {
      let b, shift = 0, result = 0;
      do { b = str.charCodeAt(idx++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
      lat += (result & 1) ? ~(result >> 1) : (result >> 1);
      shift = result = 0;
      do { b = str.charCodeAt(idx++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
      lng += (result & 1) ? ~(result >> 1) : (result >> 1);
      pts.push([lng / 1e5, -lat / 1e5]);
    }
    return pts;
  }

  return { renderRoute, renderProfile, renderDensity, renderTrends, renderCalendar, decodePolyline };
})();
