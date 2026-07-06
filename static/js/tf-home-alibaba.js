/**
 * TradeFlow Colón — home Alibaba patterns (categories modal, gateway metrics)
 */
(function () {
  'use strict';

  var modal = document.getElementById('hm-cat-modal');
  if (modal) {
    var navBtns = modal.querySelectorAll('[data-cat-panel-select]');
    var views = modal.querySelectorAll('[data-cat-panel-view]');
    var openTriggers = document.querySelectorAll('[data-cat-modal-open]');
    var closeTriggers = modal.querySelectorAll('[data-cat-modal-close]');
    var sidebarRail = document.querySelector('.hm-bento__category-list');
    var lastFocus = null;

    function showPanel(panelId) {
      var id = String(panelId || 'discover');
      views.forEach(function (view) {
        var match = view.getAttribute('data-cat-panel-view') === id;
        view.classList.toggle('is-active', match);
        view.hidden = !match;
      });
      navBtns.forEach(function (btn) {
        btn.classList.toggle('is-active', btn.getAttribute('data-cat-panel-select') === id);
      });
      if (sidebarRail) {
        sidebarRail.querySelectorAll('[data-cat-panel]').forEach(function (link) {
          link.classList.toggle('is-active', link.getAttribute('data-cat-panel') === id);
        });
      }
      var activeView = modal.querySelector('[data-cat-panel-view="' + id + '"]');
      var title = activeView ? activeView.querySelector('.hm-cat-modal__title') : null;
      if (title) {
        modal.setAttribute('aria-labelledby', title.id || 'hm-cat-modal-title');
      }
    }

    function openModal(panelId) {
      lastFocus = document.activeElement;
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('hm-cat-modal-open');
      showPanel(panelId || 'discover');
      var closeBtn = modal.querySelector('.hm-cat-modal__close');
      if (closeBtn) closeBtn.focus();
    }

    function closeModal() {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('hm-cat-modal-open');
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    openTriggers.forEach(function (trigger) {
      trigger.addEventListener('click', function (event) {
        event.preventDefault();
        openModal(trigger.getAttribute('data-cat-panel') || 'discover');
      });
    });

    closeTriggers.forEach(function (trigger) {
      trigger.addEventListener('click', function (event) {
        event.preventDefault();
        closeModal();
      });
    });

    navBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        showPanel(btn.getAttribute('data-cat-panel-select'));
      });
    });

    if (sidebarRail) {
      sidebarRail.querySelectorAll('[data-cat-modal-open]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          showPanel(btn.getAttribute('data-cat-panel') || 'discover');
        });
      });
    }

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !modal.hidden) {
        closeModal();
      }
    });
  }

  var metricsRoot = document.querySelector('[data-hm-gateway-metrics]');
  if (!metricsRoot) return;

  var counters = metricsRoot.querySelectorAll('[data-count-to]');
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function countUp(el, target, duration, delay) {
    if (target <= 0) {
      el.textContent = '0';
      return;
    }
    if (reducedMotion) {
      el.textContent = String(target);
      return;
    }
    window.setTimeout(function () {
      var start = null;
      function tick(now) {
        if (!start) start = now;
        var progress = Math.min((now - start) / duration, 1);
        el.textContent = String(Math.round(easeOutCubic(progress) * target));
        if (progress < 1) {
          window.requestAnimationFrame(tick);
        } else {
          el.textContent = String(target);
        }
      }
      window.requestAnimationFrame(tick);
    }, delay);
  }

  counters.forEach(function (el) {
    var metric = el.closest('.hm-gateway__metric');
    var index = metric ? parseInt(metric.style.getPropertyValue('--metric-i') || '0', 10) : 0;
    var target = parseInt(el.getAttribute('data-count-to'), 10);
    if (isNaN(target)) target = 0;
    countUp(el, target, 850, 350 + index * 80);
  });
})();
