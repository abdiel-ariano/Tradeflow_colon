/**
 * TradeFlow Colón — homepage interactions
 * Count-up stats, scroll reveals, transform sliders, supplier carousels, navbar shadow.
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

  /* ── Transform sliders (trending, testimonials) ── */
  function initSliders() {
    document.querySelectorAll('[data-hm-slider]').forEach(function (root) {
      var track = root.querySelector('.hm-slider__track');
      var viewport = root.querySelector('.hm-slider__viewport');
      var dotsWrap = root.querySelector('.hm-slider__dots');
      var prev = root.querySelector('.hm-slider__arrow--prev');
      var next = root.querySelector('.hm-slider__arrow--next');
      if (!track || !viewport || !dotsWrap) return;

      var slides = Array.prototype.slice.call(track.children).filter(function (el) {
        return el.nodeType === 1;
      });
      if (!slides.length) return;

      var visible = parseInt(root.getAttribute('data-hm-slider-visible'), 10) || 4;
      var current = 0;
      var maxIndex = 0;
      var interval = null;
      var autoMs = parseInt(root.getAttribute('data-hm-slider-autoplay'), 10) || 5000;

      function stride() {
        if (!slides[0]) return 280;
        var gap = parseInt(window.getComputedStyle(track).gap, 10) || 16;
        return slides[0].offsetWidth + gap;
      }

      function recalc() {
        var vpWidth = viewport.offsetWidth;
        var slideW = slides[0] ? slides[0].offsetWidth : 0;
        var gap = parseInt(window.getComputedStyle(track).gap, 10) || 16;
        if (slideW > 0) {
          visible = Math.max(1, Math.floor((vpWidth + gap) / (slideW + gap)));
        }
        maxIndex = Math.max(0, slides.length - visible);
        if (current > maxIndex) current = maxIndex;
        buildDots();
        goTo(current, false);
        updateArrows();
      }

      function buildDots() {
        dotsWrap.innerHTML = '';
        for (var i = 0; i <= maxIndex; i++) {
          var dot = document.createElement('button');
          dot.type = 'button';
          dot.className = 'hm-slider__dot' + (i === current ? ' is-active' : '');
          dot.setAttribute('aria-label', 'Slide ' + (i + 1));
          dot.addEventListener('click', (function (idx) {
            return function () {
              goTo(idx);
              restartAutoplay();
            };
          })(i));
          dotsWrap.appendChild(dot);
        }
      }

      function getDots() {
        return dotsWrap.querySelectorAll('.hm-slider__dot');
      }

      function goTo(index, animate) {
        if (index > maxIndex) index = 0;
        if (index < 0) index = maxIndex;
        current = index;
        var offset = current * stride();
        track.style.transition = animate === false || REDUCED ? 'none' : '';
        track.style.transform = 'translateX(-' + offset + 'px)';
        getDots().forEach(function (d, i) {
          d.classList.toggle('is-active', i === current);
        });
        updateArrows();
      }

      function updateArrows() {
        if (!prev || !next) return;
        prev.disabled = current <= 0;
        next.disabled = current >= maxIndex;
      }

      function nextSlide() {
        goTo(current + 1 > maxIndex ? 0 : current + 1);
      }

      function stopAutoplay() {
        if (interval) {
          clearInterval(interval);
          interval = null;
        }
      }

      function startAutoplay() {
        if (REDUCED || maxIndex <= 0) return;
        stopAutoplay();
        interval = setInterval(nextSlide, autoMs);
      }

      function restartAutoplay() {
        stopAutoplay();
        startAutoplay();
      }

      if (prev) {
        prev.addEventListener('click', function () {
          goTo(current - 1);
          restartAutoplay();
        });
      }

      if (next) {
        next.addEventListener('click', function () {
          goTo(current + 1);
          restartAutoplay();
        });
      }

      root.addEventListener('mouseenter', stopAutoplay);
      root.addEventListener('mouseleave', startAutoplay);

      var touchStart = 0;
      track.addEventListener('touchstart', function (e) {
        touchStart = e.touches[0].clientX;
        stopAutoplay();
      }, { passive: true });

      track.addEventListener('touchend', function (e) {
        var diff = touchStart - e.changedTouches[0].clientX;
        if (Math.abs(diff) > 40) {
          if (diff > 0) goTo(current + 1);
          else goTo(current - 1);
        }
        setTimeout(startAutoplay, 3000);
      }, { passive: true });

      window.addEventListener('resize', recalc);
      recalc();
      startAutoplay();
    });
  }

  /* ── Supplier scroll carousels ── */
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

  /* ── Navbar shadow on scroll ── */
  function initNavShadow() {
    var shell = document.getElementById('hm-public-nav');
    if (!shell) return;

    function onScroll() {
      shell.classList.toggle('is-scrolled', window.scrollY > 8);
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
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
    initSliders();
    initCarousels();
    initNavShadow();
    initRankingsTooltip();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
