/* django-strava · dataset
   One source of truth: DS.days (daily log Jan 1 – Jun 8, 2026).
   Headline stats, calendar, weekly trends are all DERIVED from it,
   so the dashboard can never contradict itself. */

window.DS = (function () {
  // Deterministic PRNG (mulberry32)
  function rng(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---- Daily log: Jan 1 → Jun 8, 2026 ----
  const start = new Date(2026, 0, 1);
  const end = new Date(2026, 5, 8);
  const r = rng(20260608);
  const days = [];
  let d = new Date(start);
  while (d <= end) {
    const dow = d.getDay(); // 0 Sun
    // Training rhythm: long efforts Sat/Sun, rest mostly Mon/Fri
    let pActive = [0.62, 0.42, 0.72, 0.55, 0.74, 0.38, 0.88][dow];
    const roll = r();
    let km = 0, sports = 0;
    if (roll < pActive) {
      const long = (dow === 0 || dow === 6) && r() < 0.55;
      km = long ? 14 + r() * 30 : 4 + r() * 10;
      sports = 1 + (r() < 0.18 ? 1 : 0); // occasional double day
    }
    days.push({ date: new Date(d), km, acts: km > 0 ? sports : 0 });
    d.setDate(d.getDate() + 1);
  }
  // Normalize so totals are exact and quotable
  const rawKm = days.reduce((s, x) => s + x.km, 0);
  const TARGET_KM = 1248;
  days.forEach(x => { x.km = x.km * (TARGET_KM / rawKm); });
  // Per-day elevation & time factors (trail days climb more)
  const r2 = rng(7);
  days.forEach(x => {
    if (x.km > 0) {
      const hilly = r2() < 0.4;
      x.elev = x.km * (hilly ? 48 + r2() * 40 : 8 + r2() * 14);
      x.hours = x.km / (hilly ? 8.2 : 11.5); // slower in hills
    } else { x.elev = 0; x.hours = 0; }
  });
  const rawElev = days.reduce((s, x) => s + x.elev, 0);
  days.forEach(x => { x.elev = x.elev * (42300 / rawElev); });
  const rawH = days.reduce((s, x) => s + x.hours, 0);
  days.forEach(x => { x.hours = x.hours * (118.4 / rawH); });

  // ---- Derived headline stats ----
  const totalKm = Math.round(days.reduce((s, x) => s + x.km, 0));
  const totalElev = Math.round(days.reduce((s, x) => s + x.elev, 0) / 100) * 100;
  const totalH = days.reduce((s, x) => s + x.hours, 0);
  const activeDays = days.filter(x => x.km > 0).length;
  const activities = days.reduce((s, x) => s + x.acts, 0);

  // ---- Regional areas (km sums to totalKm; acts sum to activities) ----
  const areas = [
    { name: "Bratislava & Danube banks", km: 812, share: 0.68, kind: "Road & river paths" },
    { name: "Malé Karpaty trails",       km: 214, share: 0.17, kind: "Forest singletrack" },
    { name: "High Tatras",               km: 138, share: 0.08, kind: "Alpine trail" },
    { name: "Vienna basin",              km: 84,  share: 0.07, kind: "Long road rides" },
  ];
  let remActs = activities;
  areas.forEach((a, i) => {
    a.acts = i === areas.length - 1 ? remActs : Math.round(activities * a.share);
    remActs -= a.acts;
  });

  // ---- Latest activity (hero) ----
  // 12.4 km in 1:02:14 → 5:01 /km exactly.
  const latest = {
    title: "Morning run · Devínska Kobyla",
    type: "Trail run",
    date: "Today, 7:14 AM · Jun 8, 2026",
    km: 12.4, time: "1:02:14", pace: "5:01", elev: 430,
    hr: 152, gear: "Brooks Caldera 8",
    kudos: 14,
  };

  // ---- Personal records by sport (tabbed) ----
  const records = {
    Running: [
      ["Longest run", "32.4", "km"],
      ["Best avg pace", "4:18", "/km"],
      ["Most climbing", "1,420", "m"],
      ["Furthest from home", "487", "km"],
    ],
    Cycling: [
      ["Longest ride", "142.6", "km"],
      ["Best avg speed", "31.4", "km/h"],
      ["Most climbing", "1,980", "m"],
      ["Biggest week", "286", "km"],
    ],
    Hiking: [
      ["Longest hike", "26.8", "km"],
      ["Highest point", "2,634", "m"],
      ["Most climbing", "1,890", "m"],
      ["Longest day out", "9:42", "h"],
    ],
  };

  // ---- Race predictions: PR vs predicted-from-current-form.
  // One consistent rule: form is ~1.5–2.5% faster than PR, everywhere. ----
  const predictions = [
    { dist: "5K",            pr: "21:48",   pred: "21:21" },
    { dist: "10K",           pr: "45:30",   pred: "44:38" },
    { dist: "Half marathon", pr: "1:42:10", pred: "1:40:05" },
    { dist: "Marathon",      pr: "3:42:55", pred: "3:38:10" },
  ];

  // ---- Gear: LIFETIME distance (labeled as such; never compared to YTD) ----
  const gear = [
    { name: "Brooks Caldera 8", type: "Trail shoes", added: "Feb 2025", km: 620, limit: 800, note: "replace soon" },
    { name: "Salomon Speedcross 6", type: "Trail shoes", added: "Aug 2024", km: 430, limit: 800, note: "" },
    { name: "Trek Domane SL 6", type: "Road bike", added: "Apr 2023", km: 2340, limit: 5000, note: "chain service @ 5,000" },
    { name: "Garmin Forerunner 955", type: "GPS watch", added: "Feb 2025", km: null, limit: null, note: "tracks all activities" },
  ];

  // ---- Equivalents (all derived from the two YTD totals) ----
  const equivalents = [
    { label: "Around the equator", value: (totalKm / 40075 * 100).toFixed(1) + "%", base: "of 40,075 km" },
    { label: "Everests climbed", value: "×" + (totalElev / 8849).toFixed(1), base: "of 8,849 m" },
    { label: "Marathons covered", value: "×" + (totalKm / 42.195).toFixed(0), base: "of 42.2 km" },
    { label: "Countries visited", value: "5", base: "SK · AT · CZ · HU · PL" },
  ];

  // ---- Standout effort of 2026 (distinct from latest) ----
  const standout = {
    title: "Malá Fatra ridge traverse",
    date: "May 17, 2026",
    km: "28.6", elev: "2,140", time: "4:52:08",
    gear: "Salomon Speedcross 6",
    why: [
      "Longest mountain effort of 2026",
      "Biggest single-day climb (2,140 m)",
      "Top 2% relative effort this year",
    ],
  };

  // ---- Trends: monthly (Jan 2025 – Jun 2026) & yearly ----
  const r3 = rng(99);
  const monthly = [];
  const mNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  for (let i = 0; i < 12; i++) {
    const seasonal = 0.6 + 0.5 * Math.sin((i - 2) / 12 * Math.PI * 2 + 1.2);
    monthly.push({ label: mNames[i] + " ’25", km: Math.round(120 + 140 * seasonal + r3() * 40),
                   year: 2025, month: i });
  }
  // 2026 months from the daily log
  for (let m = 0; m < 6; m++) {
    const km = days.filter(x => x.date.getMonth() === m).reduce((s, x) => s + x.km, 0);
    monthly.push({ label: mNames[m] + " ’26", km: Math.round(km), year: 2026, month: m });
  }
  monthly.forEach(m2 => {
    m2.elev = Math.round(m2.km * 33.9 / 10) * 10;
    m2.hours = +(m2.km / 10.55).toFixed(1);
  });
  const yearly = [
    { label: "2022", km: 1410 }, { label: "2023", km: 1890 },
    { label: "2024", km: 2260 }, { label: "2025", km: 2741 },
    { label: "2026*", km: totalKm, partial: true },
  ];
  yearly.forEach(y => { y.elev = Math.round(y.km * 33.9 / 100) * 100; y.hours = +(y.km / 10.55).toFixed(0); });

  // Weekly (derived from daily log → ISO-ish weeks starting Monday)
  const weekly = [];
  let wk = null;
  days.forEach(x => {
    const dow = (x.date.getDay() + 6) % 7; // Mon=0
    if (!wk || dow === 0) {
      wk = { start: new Date(x.date), km: 0, elev: 0, hours: 0 };
      weekly.push(wk);
    }
    wk.km += x.km; wk.elev += x.elev; wk.hours += x.hours;
  });
  weekly.forEach(w => {
    w.label = (w.start.getMonth() + 1) + "/" + w.start.getDate();
    w.km = Math.round(w.km); w.elev = Math.round(w.elev); w.hours = +w.hours.toFixed(1);
  });

  // ---- Route + elevation profile for hero (generated trace) ----
  const r4 = rng(424242);
  const route = [];
  let x = 8, y = 62, heading = -0.5;
  for (let i = 0; i < 90; i++) {
    heading += (r4() - 0.48) * 0.55;
    heading = Math.max(-1.5, Math.min(1.1, heading));
    x += Math.cos(heading) * 1.05;
    y += Math.sin(heading) * 1.05;
    y = Math.max(10, Math.min(86, y));
    route.push([x, y]);
  }
  const profile = [];
  for (let i = 0; i <= 60; i++) {
    const t = i / 60;
    const h = 180 + 250 * Math.exp(-Math.pow((t - 0.42) / 0.20, 2))
              + 120 * Math.exp(-Math.pow((t - 0.75) / 0.12, 2))
              + (r4() - 0.5) * 18;
    profile.push(h);
  }

  const fmtH = h => Math.floor(h) + "h " + String(Math.round((h % 1) * 60)).padStart(2, "0") + "m";

  return {
    days, totalKm, totalElev, totalH, activeDays, activities,
    areas, latest, records, predictions, gear, equivalents, standout,
    monthly, yearly, weekly, route, profile, fmtH,
  };
})();
