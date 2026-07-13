/**
 * Verified suppliers directory — client filter by company name.
 */
(function () {
  var input = document.getElementById('mkt-verified-filter');
  var grid = document.getElementById('mkt-vendor-grid');
  var empty = document.getElementById('mkt-verified-filter-empty');
  var clearBtn = document.getElementById('mkt-verified-filter-clear');
  var countEl = document.getElementById('mkt-verified-count');
  if (!input || !grid) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll('.mkt-vendor-card'));
  var total = cards.length;

  function applyFilter() {
    var q = (input.value || '').trim().toLowerCase();
    var visible = 0;
    cards.forEach(function (card) {
      var name = card.getAttribute('data-vendor-name') || '';
      var match = !q || name.indexOf(q) !== -1;
      card.hidden = !match;
      if (match) visible += 1;
    });
    if (countEl) countEl.textContent = String(visible);
    if (empty) empty.hidden = visible !== 0;
  }

  input.addEventListener('input', applyFilter);
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      input.value = '';
      applyFilter();
      input.focus();
    });
  }

  if (countEl) countEl.textContent = String(total);
})();
