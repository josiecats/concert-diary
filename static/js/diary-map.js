// Diary map (US-10): one pin per venue, sized by visit count, fitted to all pins.
// Reads pins from the JSON view in data-url. Refetches when HTMX fires "show-logged"
// or "map-changed", so a newly logged show appears without a page reload (US-4).
(function () {
  "use strict";

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function pinIcon(count) {
    var size = Math.round(22 + Math.min(count - 1, 6) * 5);
    return L.divIcon({
      className: "",
      html: '<span class="pin-count" style="width:' + size + "px;height:" + size + 'px">' + count + "</span>",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -size / 2],
    });
  }

  function popupHtml(pin) {
    var visits = pin.count === 1 ? "1 show" : pin.count + " shows";
    var items = pin.shows.map(function (s) {
      return '<li><a href="' + escapeHtml(s.url) + '">' + escapeHtml(s.artist) + "</a>" +
        '<span style="color:#BBB0D6"> on ' + escapeHtml(s.date) + "</span></li>";
    }).join("");
    return '<p style="margin:0;font-weight:700">' + escapeHtml(pin.name) + "</p>" +
      '<p style="margin:0 0 6px;color:#BBB0D6">' + escapeHtml(pin.city) + ", " + visits + "</p>" +
      '<ul style="margin:0;padding-left:1rem">' + items + "</ul>";
  }

  function initMap(el) {
    var map = L.map(el, { scrollWheelZoom: false, worldCopyJump: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    map.setView([30, -30], 2);
    var layer = L.layerGroup().addTo(map);
    var status = document.getElementById(el.dataset.statusId || "");
    var known = null;

    function load(highlightNew) {
      fetch(el.dataset.url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          layer.clearLayers();
          var added = null;
          var seen = {};
          (data.pins || []).forEach(function (pin) {
            seen[pin.venue_id] = pin.count;
            var marker = L.marker([pin.lat, pin.lng], {
              icon: pinIcon(pin.count),
              title: pin.name + ", " + pin.count + (pin.count === 1 ? " show" : " shows"),
              alt: pin.name,
              keyboard: true,
            }).bindPopup(popupHtml(pin)).addTo(layer);
            if (highlightNew && known && known[pin.venue_id] !== pin.count) added = { marker: marker, pin: pin };
          });
          known = seen;
          el.dataset.pinCount = String((data.pins || []).length);

          if (added) {
            map.setView([added.pin.lat, added.pin.lng], Math.max(map.getZoom(), 5));
            added.marker.openPopup();
            if (status) status.textContent = "Added " + added.pin.name + " to your map.";
          } else if (data.bounds) {
            var b = L.latLngBounds(data.bounds);
            if (b.getNorthEast().equals(b.getSouthWest())) map.setView(b.getCenter(), 12);
            else map.fitBounds(b, { padding: [36, 36], maxZoom: 12 });
          }
          el.dispatchEvent(new CustomEvent("diary-map:loaded", { bubbles: true }));
        })
        .catch(function () {
          if (status) status.textContent = "The map couldn't load. Refresh to try again.";
        });
    }

    load(false);
    document.body.addEventListener("show-logged", function () { load(true); });
    document.body.addEventListener("map-changed", function () { load(true); });
    el._diaryMap = map;
  }

  function boot() {
    document.querySelectorAll("[data-diary-map]").forEach(function (el) {
      if (!el._diaryMap) initMap(el);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
