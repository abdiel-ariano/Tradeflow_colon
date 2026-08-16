/**
 * Activa el ítem del rail admin según data-nav-active y persiste modo compacto.
 *
 * Collapsed mode flattens accordion groups into a pure icon strip so links
 * are never nested under dropdown headers.
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
  var groupStateKey = 'tf_adm_rail_group_open';

  function railGroups() {
    return Array.prototype.slice.call(
      rail.querySelectorAll('details.tf-rail-group')
    );
  }

  function flattenGroupsForNarrow() {
    var snapshot = [];
    railGroups().forEach(function (group) {
      snapshot.push(group.open ? '1' : '0');
      group.open = true;
      group.setAttribute('data-narrow-locked', 'true');
    });
    try {
      sessionStorage.setItem(groupStateKey, snapshot.join(','));
    } catch (e) { /* ignore */ }
  }

  function restoreGroupsFromNarrow() {
    var saved = '';
    try {
      saved = sessionStorage.getItem(groupStateKey) || '';
    } catch (e) { /* ignore */ }
    var flags = saved.split(',');
    railGroups().forEach(function (group, index) {
      group.removeAttribute('data-narrow-locked');
      if (flags.length && typeof flags[index] !== 'undefined' && flags[index] !== '') {
        group.open = flags[index] === '1';
      }
    });
  }

  function applyNarrow(on) {
    if (!shell) return;
    if (on) {
      shell.classList.add('adm-shell--rail-narrow');
      rail.setAttribute('data-rail-compact', 'true');
      flattenGroupsForNarrow();
    } else {
      shell.classList.remove('adm-shell--rail-narrow');
      rail.removeAttribute('data-rail-compact');
      restoreGroupsFromNarrow();
    }
    if (toggle) {
      toggle.setAttribute('aria-pressed', on ? 'true' : 'false');
      toggle.setAttribute('aria-label', on ? 'Expand menu' : 'Collapse menu');
      toggle.title = on ? 'Expand menu' : 'Collapse menu';
      var label = toggle.querySelector('.adm-rail-toggle-txt');
      if (label) label.textContent = on ? 'Expand' : 'Collapse';
    }
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

  // Accordion may boot after this script; re-apply flatten once ready.
  document.addEventListener('DOMContentLoaded', function () {
    if (shell && shell.classList.contains('adm-shell--rail-narrow')) {
      flattenGroupsForNarrow();
    }
  });

  var nav = rail.querySelector('.adm-rail-nav');
  if (nav && typeof MutationObserver !== 'undefined') {
    var observer = new MutationObserver(function () {
      if (shell && shell.classList.contains('adm-shell--rail-narrow')) {
        flattenGroupsForNarrow();
      }
    });
    observer.observe(nav, { childList: true, subtree: true });
  }
})();
