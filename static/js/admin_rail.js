/**
 * Activa el ítem del rail admin según data-nav-active y persiste modo compacto.
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

  var shell = document.querySelector('.adm-shell');
  var toggle = document.getElementById('admRailToggle');
  var storageKey = 'tf_adm_rail_narrow';

  function applyNarrow(on) {
    if (!shell) return;
    if (on) shell.classList.add('adm-shell--rail-narrow');
    else shell.classList.remove('adm-shell--rail-narrow');
    try {
      localStorage.setItem(storageKey, on ? '1' : '0');
    } catch (e) { /* ignore */ }
  }

  try {
    if (localStorage.getItem(storageKey) === '1') applyNarrow(true);
  } catch (e) { /* ignore */ }

  if (toggle) {
    toggle.addEventListener('click', function () {
      var on = !shell || !shell.classList.contains('adm-shell--rail-narrow');
      applyNarrow(on);
    });
  }
})();
