/* django-strava · activities page — route SVGs, view + sort controls */
function renderRoutes(root) {
  (root || document).querySelectorAll('.fc-route[data-polyline]').forEach(function(svg) {
    window.DSCharts.renderRouteSvg(svg);
  });
}
renderRoutes(document);
document.body.addEventListener('htmx:afterSwap', function(e) { renderRoutes(e.target); });

// ——— Distance range slider (dual handle) ———
// Two overlapping range inputs. We keep the handles from crossing, paint the fill
// between them and update the km readout live on `input`; the native `change` event
// (fired on release) bubbles to #acts-filters, whose hx-trigger includes `change`.
// `setCeil` lets the sport dropdown rescale the track (max distance is sport-specific).
var DSDist = (function() {
  var root = document.getElementById('dist-slider');
  if (!root) return null;
  var ceil = Number(root.dataset.ceil) || 1;
  var track = root.querySelector('.af-dist-track');
  var lo = root.querySelector('.af-dist-min');
  var hi = root.querySelector('.af-dist-max');
  var loOut = root.querySelector('.af-dist-lo');
  var hiOut = root.querySelector('.af-dist-hi');

  function paint() {
    track.style.setProperty('--lo-pct', (lo.value / ceil * 100) + '%');
    track.style.setProperty('--hi-pct', (hi.value / ceil * 100) + '%');
    loOut.textContent = lo.value;
    hiOut.textContent = hi.value;
  }

  lo.addEventListener('input', function() {
    if (Number(lo.value) > Number(hi.value)) lo.value = hi.value;
    paint();
  });
  hi.addEventListener('input', function() {
    if (Number(hi.value) < Number(lo.value)) hi.value = lo.value;
    paint();
  });
  paint();

  return {
    // Rescale to a new upper bound and reset the window to the full range — the old
    // handle positions are meaningless against a different sport's distances.
    setCeil: function(newCeil) {
      ceil = Number(newCeil) || 1;
      lo.max = hi.max = ceil;
      root.dataset.ceil = ceil;
      lo.value = 0;
      hi.value = ceil;
      paint();
    }
  };
})();

// Per-sport distance ceilings ('all' / group key / sport_type → km), see ActivitiesView.
var DSDistCeils = (function() {
  var el = document.getElementById('dist-ceils-data');
  return el ? JSON.parse(el.textContent) : {};
})();

// ——— Sport dropdown drives the filter form ———
(function() {
  var btn = document.getElementById('acts-sport-btn');
  if (btn && window.DSSport) {
    window.DSSport.build(btn, { onSelect: function(value) {
      document.getElementById('f-sport').value = value;
      // Rescale the distance slider to the newly-selected sport before submitting, so
      // the reset dist_min/dist_max ride along in the same request.
      if (DSDist) DSDist.setCeil(value in DSDistCeils ? DSDistCeils[value] : DSDistCeils.all);
      document.getElementById('acts-filters').requestSubmit();
    }});
  }
})();

function setView(view) {
  document.getElementById('view-grid').classList.toggle('active', view === 'grid');
  document.getElementById('view-table').classList.toggle('active', view === 'table');
  document.getElementById('f-view').value = view;
  document.getElementById('acts-filters').requestSubmit();
}
function setSort(key) {
  var sortInput = document.getElementById('f-sort');
  var dirInput = document.getElementById('f-dir');
  if (sortInput.value === key) {
    dirInput.value = dirInput.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortInput.value = key;
    dirInput.value = 'asc';
  }
  document.getElementById('acts-filters').requestSubmit();
}

// ——— Activity modal: clicking a table row opens that activity's card ———
// The card HTML (with its route trace) is fetched on demand from ActivityCardView,
// the same endpoint the dashboard and compare pages use.
(function() {
  var modal = document.getElementById('activity-modal');
  if (!modal) return;
  var host = modal.querySelector('.act-modal-host');

  function cardUrl(id) { return modal.dataset.cardUrl.replace('/0/card/', '/' + id + '/card/'); }

  function close() {
    modal.hidden = true;
    host.innerHTML = '';
    document.body.classList.remove('modal-open');
  }

  function open(id) {
    fetch(cardUrl(id), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function(r) { return r.ok ? r.text() : ''; })
      .then(function(html) {
        if (!html) return;
        host.innerHTML = html;
        modal.hidden = false;
        document.body.classList.add('modal-open');
        var card = host.querySelector('.float-card');
        if (!card) return;
        card.style.display = '';
        var route = card.querySelector('.fc-route[data-polyline]');
        if (route && window.DSCharts) window.DSCharts.renderRouteSvg(route);
        var closeBtn = card.querySelector('.fc-close');
        if (closeBtn) closeBtn.addEventListener('click', close);
      });
  }

  modal.querySelector('.act-modal-backdrop').addEventListener('click', close);
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && !modal.hidden) close();
  });

  // Delegate from the document so rows swapped in by the filter/sort form work too.
  document.addEventListener('click', function(e) {
    var row = e.target.closest('.at-row');
    if (row && row.dataset.activity) open(row.dataset.activity);
  });
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var row = e.target.closest('.at-row');
    if (row && row.dataset.activity) { e.preventDefault(); open(row.dataset.activity); }
  });
})();
