/**
 * Mark the active ops-rail destination from data-nav-active.
 *
 * Desktop collapse was removed: layered admin CSS made a reliable icon-only
 * rail unreliable. Accordion sections already keep the full-width menu usable.
 */
(function () {
  var rail = document.getElementById('admRail');
  if (!rail) return;

  var active = rail.getAttribute('data-nav-active') || 'dashboard';
  rail.querySelectorAll('a[data-adm-nav]').forEach(function (a) {
    if (a.getAttribute('data-adm-nav') === active) {
      a.classList.add('is-active');
    }
  });
})();
