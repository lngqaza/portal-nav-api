'use strict';
/**
 * portal.js — shared layout behaviour for the mock portal.
 * Sets active sidebar link, wires topbar search button to NavWidget.
 */
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    // Mark active sidebar link based on current path
    var path = window.location.pathname.replace(/\/+$/, '') || '/';
    document.querySelectorAll('.sidebar-link').forEach(function (el) {
      var href = (el.getAttribute('href') || '').replace(/\/+$/, '');
      if (href && (path === href || path.startsWith(href + '/'))) {
        el.classList.add('active');
      }
    });

    // Wire topbar search and sidebar search button to open the widget
    document.querySelectorAll('[data-open-nav]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        if (window.NavWidget) window.NavWidget.open();
      });
    });
  });
}());
