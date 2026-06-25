/**
 * CountUp animation for hero stats — easeOutExpo, 0.1s stagger.
 * Respects prefers-reduced-motion.
 */
(function () {
  'use strict';

  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var DURATION = 2000;

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

  function animateCounter(el, target, duration, prefix, suffix, decimals, delayMs) {
    if (prefersReducedMotion) {
      el.textContent = formatNumber(target, prefix, suffix, decimals);
      return;
    }

    var startTime = null;

    function update(currentTime) {
      if (startTime === null) startTime = currentTime;
      var elapsed = currentTime - startTime - delayMs;
      if (elapsed < 0) {
        requestAnimationFrame(update);
        return;
      }
      var progress = Math.min(elapsed / duration, 1);
      var current = target * easeOutExpo(progress);
      el.textContent = formatNumber(current, prefix, suffix, decimals);
      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }

    requestAnimationFrame(update);
  }

  function runStat(el, staggerIndex) {
    var target = parseFloat(el.dataset.target) || 0;
    var prefix = el.dataset.prefix || '';
    var suffix = el.dataset.suffix || '';
    var decimals = parseInt(el.dataset.decimals, 10) || 0;
    var delay = (staggerIndex || 0) * 100;
    animateCounter(el, target, DURATION, prefix, suffix, decimals, delay);
  }

  var numbers = document.querySelectorAll('.hero-stat-number');
  if (!numbers.length) return;

  if (!('IntersectionObserver' in window)) {
    numbers.forEach(function (el, i) { runStat(el, i); });
    return;
  }

  var grid = document.querySelector('.hero-stats-grid');
  var observed = false;

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting || observed) return;
      observed = true;
      numbers.forEach(function (el, i) { runStat(el, i); });
      observer.disconnect();
    });
  }, { threshold: 0.35 });

  observer.observe(grid || numbers[0]);
})();
