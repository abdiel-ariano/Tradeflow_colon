/**
 * TradeFlow Colón — homepage interactions
 * Count-up stats, scroll reveals, carousel arrows, rankings tooltip.
 */
(function () {
  'use strict';

  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Count-up (hero stats) ── */
  function animateCount(el, target, suffix, duration) {
    if (REDUCED) {
      el.textContent = target.toLocaleString() + (suffix || '');
      return;
    }
    var start = 0;
    var startTime = null;
    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = Math.floor(start + (target - start) * eased);
      el.textContent = value.toLocaleString() + (suffix || '');
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function initCountUp() {
    var stats = document.querySelectorAll('[data-hm-count]');
    if (!stats.length) return;

    var observer = new IntersectionObserver(
      function (entries, obs) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var el = entry.target;
          var target = parseInt(el.getAttribute('data-hm-count'), 10) || 0;
          var suffix = el.getAttribute('data-hm-suffix') || '';
          animateCount(el, target, suffix, 1500);
          obs.unobserve(el);
        });
      },
      { threshold: 0.15 }
    );

    stats.forEach(function (el) { observer.observe(el); });
  }

  /* ── Scroll reveal ── */
  function initReveal() {
    var items = document.querySelectorAll('[data-hm-reveal]');
    if (!items.length) return;

    if (REDUCED) {
      items.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );

    items.forEach(function (el) { observer.observe(el); });
  }

  /* ── Horizontal carousels ── */
  function initCarousels() {
    document.querySelectorAll('[data-hm-carousel]').forEach(function (root) {
      var track = root.querySelector('.hm-carousel__track');
      var prev = root.querySelector('.hm-carousel__arrow--prev');
      var next = root.querySelector('.hm-carousel__arrow--next');
      if (!track || !prev || !next) return;

      function scrollByDir(dir) {
        var card = track.querySelector('.hm-sp-card, .hm-trend-card');
        var amount = card ? card.offsetWidth + 12 : 280;
        track.scrollBy({ left: dir * amount, behavior: REDUCED ? 'auto' : 'smooth' });
      }

      prev.addEventListener('click', function () { scrollByDir(-1); });
      next.addEventListener('click', function () { scrollByDir(1); });

      function updateArrows() {
        var max = track.scrollWidth - track.clientWidth - 2;
        prev.disabled = track.scrollLeft <= 2;
        next.disabled = track.scrollLeft >= max;
      }

      track.addEventListener('scroll', updateArrows, { passive: true });
      updateArrows();
    });
  }

  /* ── Rankings tooltip ── */
  function initRankingsTooltip() {
    var btn = document.getElementById('hm-rankings-info');
    var tip = document.getElementById('hm-rankings-tooltip');
    if (!btn || !tip) return;

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = tip.hasAttribute('hidden');
      if (open) {
        tip.removeAttribute('hidden');
        btn.setAttribute('aria-expanded', 'true');
      } else {
        tip.setAttribute('hidden', '');
        btn.setAttribute('aria-expanded', 'false');
      }
    });

    document.addEventListener('click', function () {
      tip.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
    });
  }

  function init() {
    initCountUp();
    initReveal();
    initCarousels();
    initRankingsTooltip();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
