/* django-strava · gallery page — view toggle, sport tabs, lightbox */
// ——— View toggle (presentational, client-side) ———
let currentView = 'grid';
function applyView() {
  const g = document.getElementById('gallery-grid');
  if (!g) return;
  if (currentView === 'grid') g.removeAttribute('data-view');
  else g.setAttribute('data-view', currentView);
}
function setView(view, btn) {
  currentView = view;
  document.querySelectorAll('#view-toggle button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyView();
}

// ——— Sport dropdown drives the filter form ———
(function() {
  const btn = document.getElementById('gallery-sport-btn');
  if (btn && window.DSSport) {
    DSSport.build(btn, { onSelect: function(value) {
      document.getElementById('g-sport').value = value;
      document.getElementById('gallery-filters').requestSubmit();
    }});
  }
})();

// Re-apply the chosen layout after htmx swaps in a fresh grid.
document.body.addEventListener('htmx:afterSwap', function(e) {
  if (e.target.id === 'gallery-results') applyView();
});

// ——— Lightbox (reads data-* off the rendered cards) ———
const CAL_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="4" y="5" width="16" height="15" rx="2"></rect><line x1="8" y1="3" x2="8" y2="7"></line><line x1="16" y1="3" x2="16" y2="7"></line><line x1="4" y1="10" x2="20" y2="10"></line></svg>';
const ACT_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="6" cy="18" r="2.4"></circle><circle cx="18" cy="6" r="2.4"></circle><path d="M8 17 C 13 15, 11 8, 16 7"></path></svg>';
const DIST_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="3 20 10 7 14 13 17 9 21 20"></polyline></svg>';
let lbItems = [], lbIndex = 0;

function openLightbox(el) {
  lbItems = Array.from(document.querySelectorAll('#gallery-grid .gallery-item'));
  lbIndex = lbItems.indexOf(el);
  updateLightbox();
  document.getElementById('lightbox').classList.add('open');
  document.addEventListener('keydown', lbKeyHandler);
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
  document.removeEventListener('keydown', lbKeyHandler);
}
function closeLightboxOnBg(e) {
  if (e.target === document.getElementById('lightbox')) closeLightbox();
}
function lbNav(dir) {
  if (!lbItems.length) return;
  lbIndex = (lbIndex + dir + lbItems.length) % lbItems.length;
  updateLightbox();
}
function lbKeyHandler(e) {
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowRight') lbNav(1);
  if (e.key === 'ArrowLeft')  lbNav(-1);
}
function updateLightbox() {
  const el = lbItems[lbIndex];
  if (!el) return;
  const d = el.dataset;
  document.getElementById('lb-title').textContent = d.title;
  document.getElementById('lb-media-inner').innerHTML = d.photo
    ? '<img src="' + d.photo + '" alt="">'
    : '';
  document.getElementById('lb-meta-date').innerHTML = CAL_SVG + ' ' + d.date;
  document.getElementById('lb-meta-act').innerHTML = ACT_SVG + ' ' + d.sport;
  document.getElementById('lb-meta-dist').innerHTML = DIST_SVG + ' ' + d.dist;
}
