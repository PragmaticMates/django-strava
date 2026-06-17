/* django-strava · gear page — gear detail sheet */
const BIKE_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.0" stroke-linecap="round" stroke-linejoin="round" style="width:100px;height:100px"><circle cx="5.5" cy="15" r="3.5"></circle><circle cx="18.5" cy="15" r="3.5"></circle><polyline points="5.5 11.5 5.5 5.5 11.5 3.5 15.5 8.5 18.5 11.5"></polyline><line x1="10" y1="5.5" x2="10" y2="15"></line></svg>`;
const SHOE_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.0" stroke-linecap="round" stroke-linejoin="round" style="width:100px;height:100px"><path d="M2 17h13l5-5-3-2-3 3H9L6 9H3a1 1 0 0 0-1 1v6a1 1 0 0 0 0 1z"></path><path d="M9 17v1a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-1"></path></svg>`;

function wearColor(pct) {
  if (pct < 40) return '#22C065';
  if (pct < 75) return '#F5A623';
  return '#EE4D0D';
}

function openSheet(card) {
  const d = card.dataset;
  const wear = parseInt(d.wear) || 0;
  document.getElementById('gs-name').textContent = d.name;
  document.getElementById('gs-brand').textContent = d.brand;
  document.getElementById('gs-img-icon').innerHTML = d.icon === 'bike' ? BIKE_SVG : SHOE_SVG;
  document.getElementById('gs-stats').innerHTML = `
    <div class="gear-sheet-stat">
      <div class="gear-sheet-stat-val">${d.km}</div>
      <div class="gear-sheet-stat-lbl">km logged</div>
    </div>
    <div class="gear-sheet-stat">
      <div class="gear-sheet-stat-val">${d.rides}</div>
      <div class="gear-sheet-stat-lbl">${d.ridesLabel}</div>
    </div>
    <div class="gear-sheet-stat">
      <div class="gear-sheet-stat-val">${wear}%</div>
      <div class="gear-sheet-stat-lbl">wear</div>
    </div>`;
  document.getElementById('gs-wear-pct').textContent = wear + '%';
  const fill = document.getElementById('gs-wear-fill');
  fill.style.width = wear + '%';
  fill.style.background = wearColor(wear);
  document.getElementById('gs-last-used').textContent = d.lastUsed;
  document.getElementById('gs-type').textContent = d.type;
  document.getElementById('gear-sheet').classList.add('open');
  document.addEventListener('keydown', sheetKeyHandler);
}

function closeSheet() {
  document.getElementById('gear-sheet').classList.remove('open');
  document.removeEventListener('keydown', sheetKeyHandler);
}
function closeSheetOnBg(e) {
  if (e.target === document.getElementById('gear-sheet')) closeSheet();
}
function sheetKeyHandler(e) {
  if (e.key === 'Escape') closeSheet();
}

function toggleDir() {
  const d = document.getElementById('g-dir');
  d.value = d.value === 'asc' ? 'desc' : 'asc';
  document.getElementById('gear-filters').requestSubmit();
}
