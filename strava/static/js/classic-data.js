/* django-strava · classic skin — data series + wiring */
(function () {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];

  function rng(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const mN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

  function readJSON(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  /* ---- Trends series (real data from the server, with a demo fallback) ---- */
  // Re-read on a filter change (ds:datachanged) so the chart tracks the active filter.
  let weekly, monthly, yearly;
  function loadTrends() {
    const realTrends = readJSON("dashboard-trends");
    if (realTrends) {
      ({ weekly, monthly, yearly } = realTrends);
      return;
    }
    const r = rng(45211);
    weekly = [];
    const t0 = new Date(2025, 0, 6);
    for (let i = 0; i < 75; i++) {
      const dt = new Date(t0); dt.setDate(t0.getDate() + i * 7);
      const season = 0.55 + 0.45 * Math.sin((dt.getMonth() - 2) / 12 * Math.PI * 2 + 1.1);
      const spike = r() < 0.05 ? 1.8 : 1;
      const km = Math.max(8, Math.round((26 + 64 * season) * (0.65 + r() * 0.7) * spike));
      weekly.push({ label: mN[dt.getMonth()] + (dt.getFullYear() === 2026 ? " ’26" : ""), km, dt });
    }
    monthly = [];
    for (let i = 0; i < 18; i++) {
      const y = i < 12 ? 2025 : 2026, m = i % 12;
      const inMonth = weekly.filter(w => w.dt.getFullYear() === y && w.dt.getMonth() === m);
      monthly.push({ label: mN[m] + " ’" + String(y).slice(2), km: inMonth.reduce((s, w) => s + w.km, 0) });
    }
    yearly = [
      { label: "2022", km: 1410 }, { label: "2023", km: 1890 },
      { label: "2024", km: 2260 }, { label: "2025", km: monthly.slice(0, 12).reduce((s, m2) => s + m2.km, 0) },
      { label: "2026*", km: monthly.slice(12).reduce((s, m2) => s + m2.km, 0), partial: true },
    ];
    const r2 = rng(8);
    [weekly, monthly, yearly].forEach(set => set.forEach(x => {
      x.elev = Math.round(x.km * (26 + r2() * 16));
      x.hours = +(x.km / (9.6 + r2() * 2.2)).toFixed(1);
      x.pace = +(5.05 + r2() * 1.05).toFixed(2); // min/km
      x.acts = Math.max(1, Math.round(x.km / (12 + r2() * 6)));
    }));
  }
  loadTrends();

  /* ---- Personal records (4 sports) ---- */
  const records = {
    Running: [
      ["Longest", "32.4", "km"], ["Fastest (avg. pace)", "4:18", "/km"],
      ["Most Elevation", "1,420", "m"], ["Furthest from Home", "487", "km"],
    ],
    Cycling: [
      ["Longest", "142.6", "km"], ["Fastest (avg. speed)", "31.4", "km/h"],
      ["Most Elevation", "1,980", "m"], ["Furthest from Home", "612", "km"],
    ],
    Hiking: [
      ["Longest", "26.8", "km"], ["Highest Point", "2,634", "m"],
      ["Most Elevation", "1,890", "m"], ["Furthest from Home", "318", "km"],
    ],
    Swimming: [
      ["Longest", "3.2", "km"], ["Fastest (per 100 m)", "1:52", ""],
      ["Open Water Longest", "1.8", "km"], ["Furthest from Home", "95", "km"],
    ],
  };
  const recList = $("#rec-list");
  function showRecords(sport) {
    recList.innerHTML = records[sport].map(([k, v, u]) => `
      <div class="kv"><span class="k">${k}</span>
      <span class="v">${v}${u ? ` <small>${u}</small>` : ""}</span></div>`).join("");
    $$("#rec-tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.sport === sport));
  }
  $("#rec-tabs").addEventListener("click", e => {
    const b = e.target.closest("button"); if (b) showRecords(b.dataset.sport);
  });
  showRecords("Running");

  /* ---- Activity calendar dots (5 weeks, sizes 0–2) ---- */
  // Re-read on a filter change (ds:datachanged) so the dots track the active filter.
  function renderCalendar() {
    const weeks = readJSON("dashboard-calendar") || [
      { label: "Jun 2 – 8",      dots: [0, 0, 0, 2, 2, 2, 2] },
      { label: "Jun 9 – 15",     dots: [2, 0, 0, 0, 0, 0, 1] },
      { label: "Jun 16 – 22",    dots: [0, 0, 2, 0, 0, 0, 2] },
      { label: "Jun 23 – 29",    dots: [2, 0, 0, 0, 0, 0, 0] },
      { label: "Jun 30 – Jul 6", dots: [0, 0, 0, 0, 0, 2, 0] },
    ];
    $("#dotcal-rows").innerHTML = weeks.map(w => `
      <span class="wk">${w.label}</span>
      ${w.dots.map(s => `<span class="dot" data-s="${s}"></span>`).join("")}`).join("");
  }
  renderCalendar();

  /* ---- Charts ---- */
  const tipTrend = $("#tip-trend");
  // Render route in float card
  const fcRouteSvg = $("#fc-route-svg");
  if (fcRouteSvg && window.DS && window.DSCharts) {
    window.DSCharts.renderRoute(fcRouteSvg, window.DS.route);
  }
  const tip = $("#tip-trend");
  let metric = "km", range = "weekly";
  const rows = () => range === "weekly" ? weekly :
                     range === "monthly" ? monthly : yearly;
  function draw() { window.DSCharts.renderTrends($("#trend-host"), rows(), metric, tip); }
  draw();
  $("#seg-metric").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    metric = b.dataset.metric;
    $$("#seg-metric button").forEach(x => x.setAttribute("aria-pressed", x === b));
    draw();
  });
  $("#seg-range").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    range = b.dataset.range;
    $$("#seg-range button").forEach(x => x.setAttribute("aria-pressed", x === b));
    draw();
  });
  let rsT;
  window.addEventListener("resize", () => { clearTimeout(rsT); rsT = setTimeout(draw, 120); });
  window.addEventListener("ds:tweaks", () => requestAnimationFrame(draw));
  // A filter change swaps in fresh trends/calendar JSON — reload and redraw both.
  window.addEventListener("ds:datachanged", () => {
    loadTrends();
    renderCalendar();
    requestAnimationFrame(draw);
  });
})();
