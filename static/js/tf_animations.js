/**
 * tf_animations.js — feedback visual TradeFlow Colón
 */
(function (global) {
  'use strict';

  function injectStyles() {
    if (document.getElementById('tf-anim-styles')) return;
    var style = document.createElement('style');
    style.id = 'tf-anim-styles';
    style.textContent = [
      '@keyframes tfFadeIn{from{opacity:0}to{opacity:1}}',
      '@keyframes tfFadeOut{from{opacity:1}to{opacity:0}}',
      '@keyframes tfSlideUp{from{opacity:0;transform:translateY(30px) scale(0.95)}',
      'to{opacity:1;transform:translateY(0) scale(1)}}',
      '@keyframes tfPopIn{from{opacity:0;transform:translate(-50%,-50%) scale(0.7)}',
      'to{opacity:1;transform:translate(-50%,-50%) scale(1)}}',
      '@keyframes tfDraw{to{stroke-dashoffset:0}}',
      '@media (prefers-reduced-motion:reduce){',
      '.tf-pulse-once,.tf-confirm-pop{animation:none!important}}',
    ].join('');
    document.head.appendChild(style);
  }

  injectStyles();

  var TF = {
    success: function (mensaje, callback) {
      var overlay = document.createElement('div');
      overlay.style.cssText =
        'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;' +
        'justify-content:center;z-index:99999;animation:tfFadeIn 0.2s ease;';
      var logoSrc = (global.TF_STATIC_LOGO || '/static/img/logo-icon-color.png');
      overlay.innerHTML =
        '<div style="background:#fff;border-radius:20px;padding:2.5rem;text-align:center;' +
        'max-width:380px;width:90%;animation:tfSlideUp 0.3s cubic-bezier(0.34,1.56,0.64,1)">' +
        '<img src="' + logoSrc + '" alt="TradeFlow" style="height:56px;width:auto;margin:0 auto 1rem;object-fit:contain;" class="tf-pulse-once">' +
        '<p style="font-family:var(--tf-font-display,serif);font-size:1.25rem;color:var(--tf-dark,#0F2A44);' +
        'margin-bottom:.5rem">Listo</p>' +
        '<p style="color:var(--tf-muted,#6B7A88);font-size:.9rem">' + mensaje + '</p></div>';
      document.body.appendChild(overlay);
      setTimeout(function () {
        overlay.style.animation = 'tfFadeOut 0.2s ease forwards';
        setTimeout(function () {
          overlay.remove();
          if (callback) callback();
        }, 200);
      }, 2500);
    },

    notify: function (mensaje, tipo) {
      tipo = tipo || 'info';
      var colores = {
        info: { bg: '#e8f4f6', border: '#2E5B8A', text: '#0F2A44' },
        success: { bg: '#e8f5e9', border: '#2e7d32', text: '#2e7d32' },
        warning: { bg: '#fff8e1', border: '#f5a623', text: '#8b6914' },
        error: { bg: '#fde8e8', border: '#c62828', text: '#c62828' },
      };
      var c = colores[tipo] || colores.info;
      var notif = document.createElement('div');
      notif.setAttribute('role', 'status');
      notif.style.cssText =
        'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%) scale(0.8);' +
        'background:' + c.bg + ';border:2px solid ' + c.border + ';color:' + c.text + ';' +
        'padding:1.25rem 2rem;border-radius:16px;font-size:1rem;font-weight:600;' +
        'box-shadow:0 20px 60px rgba(0,0,0,0.2);z-index:99999;text-align:center;max-width:360px;' +
        'animation:tfPopIn 0.3s cubic-bezier(0.34,1.56,0.64,1) forwards;';
      notif.textContent = mensaje;
      document.body.appendChild(notif);
      notif.addEventListener('click', function () {
        notif.style.animation = 'tfFadeOut 0.2s ease forwards';
        setTimeout(function () { notif.remove(); }, 200);
      });
      setTimeout(function () {
        if (notif.parentNode) {
          notif.style.animation = 'tfFadeOut 0.25s ease forwards';
          setTimeout(function () { notif.remove(); }, 250);
        }
      }, 4000);
    },

    confirm: function (opciones) {
      var o = opciones || {};
      var overlay = document.createElement('div');
      overlay.style.cssText =
        'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;' +
        'justify-content:center;z-index:99999;';
      overlay.innerHTML =
        '<div style="background:#fff;border-radius:20px;padding:2rem;max-width:400px;width:90%">' +
        '<h3 style="font-family:var(--tf-font-display,serif);color:var(--tf-dark,#0F2A44);margin:0 0 .75rem">' +
        (o.titulo || 'Confirmar acción') + '</h3>' +
        '<p style="color:var(--tf-muted);margin-bottom:1.5rem">' + (o.mensaje || '¿Estás seguro?') + '</p>' +
        '<div style="display:flex;gap:.75rem;justify-content:flex-end">' +
        '<button type="button" id="tf-cancel-btn" class="btn-tf btn-secondary-tf">Cancelar</button>' +
        '<button type="button" id="tf-confirm-btn" class="btn-tf btn-primary-tf">Confirmar</button>' +
        '</div></div>';
      document.body.appendChild(overlay);
      overlay.querySelector('#tf-cancel-btn').onclick = function () {
        overlay.remove();
        if (o.onCancelar) o.onCancelar();
      };
      overlay.querySelector('#tf-confirm-btn').onclick = function () {
        overlay.remove();
        if (o.onAceptar) o.onAceptar();
      };
    },
  };

  global.TF = TF;
})(typeof window !== 'undefined' ? window : this);
