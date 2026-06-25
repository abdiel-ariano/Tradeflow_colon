/**
 * CountUp for primary hero stat — easeOutExpo, 2.5s.
 * Secondary stats fade in via CSS after primary reveals.
 */
(function () {
  'use strict';

  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var DURATION = 2500;

  function easeOutExpo(t) {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }

  function formatNumber(num, prefix, suffix, decimals) {
    var n = parseFloat(num) || 0;
    var formatted = n.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
    return (prefix || '') + formatted + (suffix || '');
  }

  function animateCounter(el, target, duration, prefix, suffix, decimals) {
    if (prefersReducedMotion) {
      el.textContent = formatNumber(target, prefix, suffix, decimals);
      revealSecondary();
      return;
    }

    var startTime = null;

    function update(currentTime) {
      if (startTime === null) startTime = currentTime;
      var elapsed = currentTime - startTime;
      var progress = Math.min(elapsed / duration, 1);
      var current = target * easeOutExpo(progress);
      el.textContent = formatNumber(current, prefix, suffix, decimals);
      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        revealSecondary();
      }
    }

    requestAnimationFrame(update);
  }

  function revealSecondary() {
    var primary = document.querySelector('.hero-stat-primary');
    var cards = document.querySelectorAll('.hero-stat-card--secondary');
    if (primary) primary.classList.add('is-revealed');
    cards.forEach(function (card) {
      card.classList.add('is-revealed');
    });
  }

  var primaryEl = document.querySelector('.hero-stat-number--primary');
  if (!primaryEl) return;

  function runPrimary() {
    var target = parseFloat(primaryEl.dataset.target) || 0;
    var prefix = primaryEl.dataset.prefix || '';
    var suffix = primaryEl.dataset.suffix || '';
    var decimals = parseInt(primaryEl.dataset.decimals, 10) || 0;
    animateCounter(primaryEl, target, DURATION, prefix, suffix, decimals);
  }

  if (!('IntersectionObserver' in window)) {
    runPrimary();
    return;
  }

  var observed = false;
  var section = document.querySelector('.hero-stats-section');

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting || observed) return;
      observed = true;
      runPrimary();
      observer.disconnect();
    });
  }, { threshold: 0.35 });

  observer.observe(section || primaryEl);
})();
