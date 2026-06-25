/**
 * TradeFlow public carousels — trending dots + premium supplier rows.
 */
(function () {
  'use strict';

  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Trending carousel ── */
  (function initTrending() {
    var track = document.querySelector('.trending-track');
    var dots = document.querySelectorAll('.trending-dot');
    if (!track || !dots.length) return;

    var cards = track.querySelectorAll('.trending-card');
    var total = cards.length;
    if (!total) return;

    var current = 0;
    var interval = null;

    function cardStride() {
      var gap = parseInt(window.getComputedStyle(track).gap, 10) || 16;
      return cards[0].offsetWidth + gap;
    }

    function scrollTo(index) {
      if (index >= total) index = 0;
      if (index < 0) index = total - 1;
      cards[index].scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', inline: 'start', block: 'nearest' });
      dots.forEach(function (d, i) { d.classList.toggle('active', i === index); });
      current = index;
    }

    function startAuto() {
      if (reducedMotion) return;
      stopAuto();
      interval = window.setInterval(function () { scrollTo(current + 1); }, 5000);
    }

    function stopAuto() {
      if (interval) {
        window.clearInterval(interval);
        interval = null;
      }
    }

    track.addEventListener('mouseenter', stopAuto);
    track.addEventListener('mouseleave', startAuto);
    track.addEventListener('touchstart', stopAuto, { passive: true });
    track.addEventListener('touchend', function () {
      window.setTimeout(startAuto, 3000);
    }, { passive: true });

    track.addEventListener('scroll', function () {
      var stride = cardStride();
      if (!stride) return;
      var newIndex = Math.round(track.scrollLeft / stride);
      if (newIndex !== current && newIndex >= 0 && newIndex < total) {
        current = newIndex;
        dots.forEach(function (d, i) { d.classList.toggle('active', i === current); });
      }
    });

    dots.forEach(function (dot, i) {
      dot.addEventListener('click', function () {
        scrollTo(i);
        stopAuto();
        startAuto();
      });
    });

    startAuto();
  })();

  /* ── Premium company row auto-scroll (alternating directions, 8s) ── */
  (function initPremiumRows() {
    if (reducedMotion) return;

    document.querySelectorAll('[data-premium-row]').forEach(function (row, idx) {
      var items = row.querySelectorAll('.premium-mini');
      if (!items.length || row.scrollWidth <= row.clientWidth) return;

      var direction = idx % 2 === 0 ? 1 : -1;
      var paused = false;
      var timer = null;

      function stride() {
        var gap = parseInt(window.getComputedStyle(row).gap, 10) || 8;
        return items[0].offsetWidth + gap;
      }

      function step() {
        if (paused) return;
        var move = stride();
        var maxScroll = row.scrollWidth - row.clientWidth;
        if (direction > 0) {
          if (row.scrollLeft >= maxScroll - 2) {
            row.scrollTo({ left: 0, behavior: 'smooth' });
          } else {
            row.scrollBy({ left: move, behavior: 'smooth' });
          }
        } else if (row.scrollLeft <= 2) {
          row.scrollTo({ left: maxScroll, behavior: 'smooth' });
        } else {
          row.scrollBy({ left: -move, behavior: 'smooth' });
        }
      }

      function start() {
        stop();
        timer = window.setInterval(step, 8000);
      }

      function stop() {
        if (timer) {
          window.clearInterval(timer);
          timer = null;
        }
      }

      row.addEventListener('mouseenter', function () { paused = true; });
      row.addEventListener('mouseleave', function () { paused = false; });
      row.addEventListener('touchstart', function () { paused = true; }, { passive: true });
      row.addEventListener('touchend', function () { paused = false; }, { passive: true });

      start();
    });
  })();
})();
