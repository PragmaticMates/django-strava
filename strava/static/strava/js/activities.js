/* django-strava · activities page — route SVGs, view + sort controls */
function renderRoutes(root) {
  (root || document).querySelectorAll('.fc-route[data-polyline]').forEach(function(svg) {
    window.DSCharts.renderRouteSvg(svg);
  });
}
renderRoutes(document);
document.body.addEventListener('htmx:afterSwap', function(e) { renderRoutes(e.target); });

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
