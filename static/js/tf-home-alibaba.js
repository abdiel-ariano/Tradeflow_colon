/**
 * TradeFlow Colón — home Alibaba patterns (categories modal, bento triggers)
 */
(function () {
  'use strict';

  var modal = document.getElementById('hm-cat-modal');

  if (modal) {
  var backdrop = modal.querySelector('.hm-cat-modal__backdrop');
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
    if (event.key === 'Escape' && modal && !modal.hidden) {
      closeModal();
    }
  });
  }

  /* Hero carousel */
  var carousel = document.querySelector('[data-hm-hero-carousel]');
  if (carousel) {
    var slides = carousel.querySelectorAll('.hm-hero-carousel__slide');
    var dots = carousel.querySelectorAll('[data-hm-hero-dot]');
    var prev = carousel.querySelector('[data-hm-hero-prev]');
    var next = carousel.querySelector('[data-hm-hero-next]');
    var index = 0;
    var timer = null;

    function showSlide(i) {
      if (!slides.length) return;
      index = (i + slides.length) % slides.length;
      slides.forEach(function (slide, idx) {
        slide.classList.toggle('is-active', idx === index);
      });
      dots.forEach(function (dot) {
        dot.classList.toggle('is-active', Number(dot.getAttribute('data-hm-hero-dot')) === index);
      });
    }

    function startAuto() {
      if (slides.length < 2) return;
      stopAuto();
      timer = window.setInterval(function () {
        showSlide(index + 1);
      }, 6000);
    }

    function stopAuto() {
      if (timer) window.clearInterval(timer);
      timer = null;
    }

    if (prev) prev.addEventListener('click', function () { showSlide(index - 1); startAuto(); });
    if (next) next.addEventListener('click', function () { showSlide(index + 1); startAuto(); });
    dots.forEach(function (dot) {
      dot.addEventListener('click', function () {
        showSlide(Number(dot.getAttribute('data-hm-hero-dot')));
        startAuto();
      });
    });
    carousel.addEventListener('mouseenter', stopAuto);
    carousel.addEventListener('mouseleave', startAuto);
    startAuto();
  }

})();
