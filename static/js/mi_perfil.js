(function () {
  'use strict';

  var root = document.getElementById('perfil-root');
  if (!root) return;

  root.classList.add('perfil-js');
  var role = root.getAttribute('data-role') || 'buyer';
  var activeTab = root.getAttribute('data-active-tab') || 'personal';

  var labels = {
    buyer: 'Buyer',
    seller: 'Seller',
    admin: 'Administrator',
  };

  var badge = document.getElementById('perfil-role-badge');
  if (badge) {
    badge.textContent = labels[role] || labels.buyer;
    badge.className = 'perfil-badge perfil-badge-' + (
      role === 'seller' ? 'seller' : (role === 'admin' ? 'admin' : 'buyer')
    );
  }

  document.querySelectorAll('[data-role-panel]').forEach(function (el) {
    if (el.getAttribute('data-role-panel') === role) {
      el.classList.add('is-visible');
    }
  });

  var statusLabels = {
    pending: 'Pending',
    paid: 'Paid',
    packed: 'Packed',
    shipped: 'Shipped',
    delivered: 'Delivered',
    cancelled: 'Cancelled',
  };
  var stEl = document.getElementById('perfil-ultima-estado');
  if (stEl) {
    var st = stEl.getAttribute('data-status') || '';
    stEl.textContent = statusLabels[st] || st;
  }

  var tabs = Array.prototype.slice.call(document.querySelectorAll('.perfil-tab'));
  var panels = Array.prototype.slice.call(document.querySelectorAll('.perfil-panel[data-tab-panel]'));

  function activateTab(tabName, focusTab) {
    tabs.forEach(function (tab) {
      var isActive = tab.getAttribute('data-tab') === tabName;
      tab.classList.toggle('is-active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
      if (focusTab && isActive) tab.focus();
    });
    panels.forEach(function (panel) {
      var isActive = panel.getAttribute('data-tab-panel') === tabName;
      panel.classList.toggle('is-active', isActive);
      if (isActive) {
        panel.removeAttribute('hidden');
      } else {
        panel.setAttribute('hidden', 'hidden');
      }
    });
    if (window.history && window.history.replaceState) {
      var url = new URL(window.location.href);
      url.searchParams.set('tab', tabName);
      window.history.replaceState({}, '', url.toString());
    }
  }

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function (event) {
      event.preventDefault();
      activateTab(tab.getAttribute('data-tab'), false);
    });
    tab.addEventListener('keydown', function (event) {
      var idx = tabs.indexOf(tab);
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        tabs[(idx + 1) % tabs.length].focus();
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        tabs[(idx - 1 + tabs.length) % tabs.length].focus();
      } else if (event.key === 'Home') {
        event.preventDefault();
        tabs[0].focus();
      } else if (event.key === 'End') {
        event.preventDefault();
        tabs[tabs.length - 1].focus();
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activateTab(tab.getAttribute('data-tab'), false);
      }
    });
  });

  activateTab(activeTab, false);

  var newPw = document.getElementById('pf_new');
  var bar = document.getElementById('perfil-strength-bar');
  if (newPw && bar) {
    newPw.addEventListener('input', function () {
      var v = newPw.value || '';
      var score = 0;
      if (v.length >= 8) score = 1;
      if (v.length >= 12) score = 2;
      if (/[0-9]/.test(v) && /[^A-Za-z0-9]/.test(v) && v.length >= 12) score = 3;
      var colors = ['#EF4444', '#EAB308', '#22C55E'];
      var widths = ['33%', '66%', '100%'];
      bar.style.width = v.length ? widths[Math.min(score, 2)] : '0';
      bar.style.background = v.length ? colors[Math.min(score, 2)] : 'transparent';
    });
  }
})();
