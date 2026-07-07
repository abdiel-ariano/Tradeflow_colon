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

  var metricsPanel = metricsRoot.querySelector('.hm-gateway__pulse-panel');
  var valueEls = metricsRoot.querySelectorAll('[data-count-to]');
  var streamFill = metricsRoot.querySelector('.hm-gateway__pulse-stream-fill');
  var streamShine = metricsRoot.querySelector('.hm-gateway__pulse-stream-shine');
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var played = false;
  var streamRafId = null;

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function formatCount(value) {
    return value.toLocaleString('en-US');
  }

  function countDuration(target) {
    if (target <= 0) return 0;
    return Math.min(1000, Math.max(600, 450 + Math.log10(target + 1) * 160));
  }

  function setStreamShinePosition(elapsed) {
    if (!streamShine) return;
    var sweepDuration = 2400;
    var loop = (elapsed % sweepDuration) / sweepDuration;
    var x = -110 + loop * 320;
    streamShine.style.transform = 'translateX(' + x + '%)';
  }

  function animateStream() {
    if (!streamFill) return;

    if (reducedMotion) {
      streamFill.style.transform = 'scaleX(1)';
      if (metricsPanel) metricsPanel.classList.add('is-streaming');
      return;
    }

    var streamDuration = 2800;
    var streamStart = null;

    function frame(now) {
      if (!streamStart) streamStart = now;
      var elapsed = now - streamStart;
      var fillProgress = Math.min(elapsed / streamDuration, 1);

      streamFill.style.transform = 'scaleX(' + fillProgress + ')';
      setStreamShinePosition(elapsed);

      if (streamShine) {
        streamShine.style.opacity = fillProgress > 0.03 ? '1' : '0';
      }

      streamRafId = window.requestAnimationFrame(frame);

      if (fillProgress >= 1) {
        streamFill.style.transform = 'scaleX(1)';
        if (metricsPanel) metricsPanel.classList.add('is-streaming');
      }
    }

    streamRafId = window.requestAnimationFrame(frame);
  }

  function countUp(el, index) {
    var cell = el.closest('.hm-gateway__pulse-cell') || el.closest('.hm-gateway__pulse-hero');
    var cellFill = cell ? cell.querySelector('.hm-gateway__pulse-cell-fill') : null;
    var caption = cell ? cell.querySelector('.hm-gateway__pulse-caption') : null;
    var target = parseInt(el.getAttribute('data-count-to'), 10);
    if (isNaN(target)) target = 0;
    var fillOrigin = window.matchMedia('(max-width: 900px)').matches ? 'left' : 'right';

    el.style.minWidth = formatCount(target).length + 'ch';

    if (reducedMotion || target <= 0) {
      el.textContent = formatCount(target);
      el.classList.add('is-live');
      if (cell && caption) {
        cell.setAttribute('aria-label', caption.textContent + ': ' + formatCount(target));
      }
      if (cellFill) cellFill.style.transform = 'scaleX(1)';
      return;
    }

    var delay = index === 0 ? 220 : 520 + (index - 1) * 120;
    var duration = countDuration(target);

    window.setTimeout(function () {
      var start = null;

      function frame(now) {
        if (!start) start = now;
        var progress = Math.min((now - start) / duration, 1);
        var eased = easeOutCubic(progress);
        var current = Math.round(eased * target);

        el.textContent = formatCount(current);
        if (cellFill) {
          cellFill.style.transform = 'scaleX(' + eased + ')';
          cellFill.style.transformOrigin = fillOrigin + ' center';
        }

        if (progress < 1) {
          window.requestAnimationFrame(frame);
        } else {
          el.textContent = formatCount(target);
          el.classList.add('is-live');
          if (cellFill) cellFill.style.transform = 'scaleX(1)';
          if (cell && caption) {
            cell.setAttribute('aria-label', caption.textContent + ': ' + formatCount(target));
          }
        }
      }

      window.requestAnimationFrame(frame);
    }, delay);
  }

  function initGatewayCarousel() {
    var carousel = metricsRoot.querySelector('[data-hm-gateway-carousel]');
    if (!carousel || carousel.dataset.hmGatewayReady === '1') return;
    carousel.dataset.hmGatewayReady = '1';

    var slides = carousel.querySelectorAll('.hm-gateway__carousel-slide');
    if (!slides.length) return;

    var dots = carousel.querySelectorAll('[data-hm-gateway-dot]');
    var prevBtn = carousel.querySelector('[data-hm-gateway-prev]');
    var nextBtn = carousel.querySelector('[data-hm-gateway-next]');
    var current = 0;
    var timer = null;
    var autoplayMs = 3800;

    function setActive(index) {
      var next = (index + slides.length) % slides.length;
      slides[current].classList.remove('is-active');
      if (dots[current]) {
        dots[current].classList.remove('is-active');
        dots[current].setAttribute('aria-selected', 'false');
      }
      current = next;
      slides[current].classList.add('is-active');
      if (dots[current]) {
        dots[current].classList.add('is-active');
        dots[current].setAttribute('aria-selected', 'true');
      }
    }

    function startAutoplay() {
      if (timer) window.clearInterval(timer);
      if (reducedMotion || slides.length < 2) return;
      timer = window.setInterval(function () {
        setActive(current + 1);
      }, autoplayMs);
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        setActive(current - 1);
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        setActive(current + 1);
      });
    }

    dots.forEach(function (dot) {
      dot.addEventListener('click', function () {
        var index = parseInt(dot.getAttribute('data-hm-gateway-dot'), 10);
        if (!isNaN(index)) setActive(index);
      });
    });

    startAutoplay();
  }

  initGatewayCarousel();

  function playMetrics() {
    if (!metricsPanel || played) return;
    played = true;
    metricsPanel.classList.add('is-visible');
    animateStream();
    valueEls.forEach(function (el, index) {
      var metricIndex = parseInt(el.getAttribute('data-metric-i'), 10);
      if (isNaN(metricIndex)) {
        var pulseCell = el.closest('.hm-gateway__pulse-cell');
        metricIndex = pulseCell
          ? parseInt(pulseCell.getAttribute('data-metric-i'), 10)
          : index;
      }
      if (isNaN(metricIndex)) metricIndex = index;
      countUp(el, metricIndex);
    });
  }

  if (reducedMotion) {
    playMetrics();
    return;
  }

  if (typeof IntersectionObserver !== 'undefined') {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          playMetrics();
          observer.disconnect();
        }
      });
    }, { threshold: 0.2 });
    observer.observe(metricsRoot);
  }

  window.requestAnimationFrame(playMetrics);
})();
