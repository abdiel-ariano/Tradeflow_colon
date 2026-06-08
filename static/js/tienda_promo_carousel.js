/**
 * TradeFlow — Active deals carousel (autoplay, arrows, dots).
 */
(function () {
  'use strict';

  var root = document.getElementById('bp-promo-carousel');
  var track = document.getElementById('bp-promo-track');
  var prevBtn = document.getElementById('bp-promo-prev');
  var nextBtn = document.getElementById('bp-promo-next');
  var dotsRoot = document.getElementById('bp-promo-dots');
  if (!root || !track) return;

  var cards = track.querySelectorAll('.bp-promo-card');
  if (cards.length < 2) {
    if (prevBtn) prevBtn.style.display = 'none';
    if (nextBtn) nextBtn.style.display = 'none';
    return;
  }

  var AUTOPLAY_MS = 4500;
  var timer = null;
  var paused = false;
  var dotButtons = [];

  function scrollStep() {
    var card = cards[0];
    if (!card) return track.clientWidth * 0.85;
    var style = window.getComputedStyle(track);
    var gap = parseFloat(style.columnGap || style.gap || '16') || 16;
    return card.offsetWidth + gap;
  }

  function maxScroll() {
    return Math.max(0, track.scrollWidth - track.clientWidth);
  }

  function pageCount() {
    var step = scrollStep();
    if (step <= 0) return 1;
    return Math.max(1, Math.ceil((maxScroll() + 1) / step) + 1);
  }

  function currentPageIndex() {
    var step = scrollStep();
    if (step <= 0) return 0;
    return Math.min(pageCount() - 1, Math.round(track.scrollLeft / step));
  }

  function buildDots() {
    if (!dotsRoot) return;
    dotsRoot.innerHTML = '';
    dotButtons = [];
    var count = pageCount();
    if (count <= 1) {
      dotsRoot.style.display = 'none';
      return;
    }
    dotsRoot.style.display = 'flex';
    for (var i = 0; i < count; i += 1) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'bp-promo-dot' + (i === 0 ? ' is-active' : '');
      btn.setAttribute('aria-label', 'Go to slide ' + (i + 1));
      btn.setAttribute('role', 'tab');
      btn.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
      (function (index) {
        btn.addEventListener('click', function () {
          track.scrollTo({ left: index * scrollStep(), behavior: 'smooth' });
          updateUi();
          restartAutoplay();
        });
      })(i);
      dotsRoot.appendChild(btn);
      dotButtons.push(btn);
    }
  }

  function updateUi() {
    var atStart = track.scrollLeft <= 2;
    var atEnd = track.scrollLeft >= maxScroll() - 2;
    if (prevBtn) prevBtn.disabled = atStart && pageCount() <= 1;
    if (nextBtn) nextBtn.disabled = atEnd && pageCount() <= 1;

    var active = currentPageIndex();
    dotButtons.forEach(function (dot, i) {
      var on = i === active;
      dot.classList.toggle('is-active', on);
      dot.setAttribute('aria-selected', on ? 'true' : 'false');
    });
  }

  function scrollNext() {
    var step = scrollStep();
    var next = track.scrollLeft + step;
    if (next >= maxScroll() - 2) {
      track.scrollTo({ left: 0, behavior: 'smooth' });
    } else {
      track.scrollTo({ left: next, behavior: 'smooth' });
    }
    window.setTimeout(updateUi, 320);
  }

  function scrollPrev() {
    var step = scrollStep();
    var prev = track.scrollLeft - step;
    if (prev <= 0) {
      track.scrollTo({ left: maxScroll(), behavior: 'smooth' });
    } else {
      track.scrollTo({ left: prev, behavior: 'smooth' });
    }
    window.setTimeout(updateUi, 320);
  }

  function stopAutoplay() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function startAutoplay() {
    stopAutoplay();
    if (paused || pageCount() <= 1) return;
    timer = window.setInterval(scrollNext, AUTOPLAY_MS);
  }

  function restartAutoplay() {
    stopAutoplay();
    startAutoplay();
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      scrollPrev();
      restartAutoplay();
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      scrollNext();
      restartAutoplay();
    });
  }

  root.addEventListener('mouseenter', function () {
    paused = true;
    stopAutoplay();
  });
  root.addEventListener('mouseleave', function () {
    paused = false;
    startAutoplay();
  });
  root.addEventListener('focusin', function () {
    paused = true;
    stopAutoplay();
  });
  root.addEventListener('focusout', function () {
    if (!root.contains(document.activeElement)) {
      paused = false;
      startAutoplay();
    }
  });

  track.addEventListener('scroll', function () {
    window.requestAnimationFrame(updateUi);
  }, { passive: true });

  window.addEventListener('resize', function () {
    buildDots();
    updateUi();
  });

  buildDots();
  updateUi();
  startAutoplay();
})();
