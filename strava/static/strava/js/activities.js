/* django-strava · activities page — route SVGs, view + sort controls */
function renderRoutes(root) {
  (root || document).querySelectorAll('.fc-route[data-polyline]').forEach(function(svg) {
    window.DSCharts.renderRouteSvg(svg);
  });
}
renderRoutes(document);
document.body.addEventListener('htmx:afterSwap', function(e) { renderRoutes(e.target); });

// ——— Sport dropdown drives the filter form ———
(function() {
  var btn = document.getElementById('acts-sport-btn');
  if (btn && window.DSSport) {
    window.DSSport.build(btn, { onSelect: function(value) {
      document.getElementById('f-sport').value = value;
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
