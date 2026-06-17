/* django-strava · classic skin — data series + wiring */
(function () {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];

  function readJSON(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  /* ---- Trends series (real data from the server) ---- */
  // Re-read on a filter change (ds:datachanged) so the chart tracks the active filter.
  let weekly = [], monthly = [], yearly = [];
  function loadTrends() {
    const realTrends = readJSON("dashboard-trends") || {};
    weekly = realTrends.weekly || [];
    monthly = realTrends.monthly || [];
    yearly = realTrends.yearly || [];
  }
  loadTrends();

  /* ---- Personal records (per sport, real data from the server) ---- */
  // Each record is tied to the activity that set it; clicking a row opens that
  // activity's card (window.openActivityModal). Re-read on a filter change so the
  // records track the active filter like every other section.
  let records = readJSON("dashboard-records") || {};
  let recSport = "Running";
  const recList = $("#rec-list");
  function showRecords(sport) {
    recSport = sport;
    const rows = records[sport] || [];
    recList.innerHTML = rows.length
      ? rows.map(r => `
          <div class="kv kv-record" role="button" tabindex="0" data-activity="${r.id}"
               title="View activity">
            <span class="k">${r.label}</span>
            <span class="v">${r.value}${r.unit ? ` <small>${r.unit}</small>` : ""}</span>
          </div>`).join("")
      : `<div class="rec-empty">No ${sport.toLowerCase()} activities yet.</div>`;
    $$("#rec-tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.sport === sport));
  }
  $("#rec-tabs").addEventListener("click", e => {
    const b = e.target.closest("button"); if (b) showRecords(b.dataset.sport);
  });
  function openRecord(row) {
    if (row && row.dataset.activity && window.openActivityModal) {
      window.openActivityModal(row.dataset.activity);
    }
  }
  recList.addEventListener("click", e => openRecord(e.target.closest(".kv-record")));
  recList.addEventListener("keydown", e => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const row = e.target.closest(".kv-record");
    if (row) { e.preventDefault(); openRecord(row); }
  });
  showRecords(recSport);
  // A filter change swaps in fresh records JSON — reload and re-render the active tab.
  window.addEventListener("ds:datachanged", () => {
    records = readJSON("dashboard-records") || {};
    showRecords(recSport);
  });

  /* ---- Activity calendar dots (5 weeks, sizes 0–2) ---- */
  // Re-read on a filter change (ds:datachanged) so the dots track the active filter.
  function renderCalendar() {
    const weeks = readJSON("dashboard-calendar") || [];
    $("#dotcal-rows").innerHTML = weeks.map(w => `
      <span class="wk">${w.label}</span>
      ${w.dots.map(s => `<span class="dot" data-s="${s}"></span>`).join("")}`).join("");
  }
  renderCalendar();

  /* ---- Charts ---- */
  const tip = $("#tip-trend");
  let metric = "km", range = "weekly";
  const rows = () => range === "weekly" ? weekly :
                     range === "monthly" ? monthly : yearly;
  function draw() {
    const host = $("#trend-host");
    const data = rows();
    if (!data.length) { host.innerHTML = '<div class="chart-empty">No activity data yet.</div>'; return; }
    window.DSCharts.renderTrends(host, data, metric, tip);
  }
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
