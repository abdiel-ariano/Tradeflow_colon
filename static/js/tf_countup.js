/**
 * CountUp animation for hero stats.
 * Respects prefers-reduced-motion.
 */
(function () {
  'use strict';

  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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
      return;
    }

    var startTime = performance.now();
    var startValue = 0;

    function update(currentTime) {
      var elapsed = currentTime - startTime;
      var progress = Math.min(elapsed / duration, 1);
      var eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      var current = startValue + (target - startValue) * eased;
      el.textContent = formatNumber(current, prefix, suffix, decimals);

      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }

    requestAnimationFrame(update);
  }

  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.hero-stat-number').forEach(function (el) {
      var target = parseFloat(el.dataset.target) || 0;
      animateCounter(el, target, 0, el.dataset.prefix || '', el.dataset.suffix || '', parseInt(el.dataset.decimals, 10) || 0);
    });
    return;
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      var target = parseFloat(el.dataset.target) || 0;
      var prefix = el.dataset.prefix || '';
      var suffix = el.dataset.suffix || '';
      var decimals = parseInt(el.dataset.decimals, 10) || 0;
      animateCounter(el, target, 2000, prefix, suffix, decimals);
      observer.unobserve(el);
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.hero-stat-number').forEach(function (el) {
    observer.observe(el);
  });
})();
