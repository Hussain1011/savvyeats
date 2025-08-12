frappe.ui.form.on('Address', {
  refresh(frm) {
    if (frm.is_new() || !frm._mapInitialized) {
      render_delivery_map(frm);
    }
  }
});

function render_delivery_map(frm) {
  const field = frm.get_field('map');
  if (!field) return;

  const container = $(`
    <div style="display:flex; flex-direction:column; gap:8px;">
      <div style="display:flex; gap:8px; align-items:center;">
        <input id="gmaps-search" type="text" placeholder="Search location…"
               style="flex:1;height:36px;padding:6px 10px;border:1px solid #d1d8dd;border-radius:6px;">
        <button id="btn-locate" type="button"
                style="height:36px;padding:0 12px;border:1px solid #4c8bf5;border-radius:6px;background:#4c8bf5;color:#fff;">
          Use current location
        </button>
      </div>
      <div id="gmaps-canvas" style="height:380px;border-radius:8px;"></div>
      <div style="font-size:12px;color:#6c757d;">Search or click map to set the delivery point. Lat/Long will auto-fill.</div>
    </div>
  `);

  field.$wrapper.empty().append(container);

  // Load Google Maps SDK once, then init
  load_google_maps(() => init_map(frm));

  // Wire the locate button
  $('#btn-locate').on('click', () => locate_user(frm));

  frm._mapInitialized = true;
}

function load_google_maps(cb) {
  if (window.google && window.google.maps) { cb(); return; }
  const scriptId = 'gmaps-sdk';
  if (document.getElementById(scriptId)) {
    const iv = setInterval(() => {
      if (window.google && window.google.maps) { clearInterval(iv); cb(); }
    }, 200);
    return;
  }
  const s = document.createElement('script');
  s.id = scriptId;
  s.src = 'https://maps.googleapis.com/maps/api/js?key=AIzaSyDRg_M7g7y3L3wSqPEcteVah14LEcwNIFg&libraries=places';
  s.async = true;
  s.defer = true;
  s.onload = cb;
  document.head.appendChild(s);
}

let map, marker, autocomplete, accuracyCircle;

function init_map(frm) {
  const lat = frm.doc.latitude ? Number(frm.doc.latitude) : 25.2854; // Doha default
  const lng = frm.doc.longitude ? Number(frm.doc.longitude) : 51.5310;
  const center = { lat, lng };

  map = new google.maps.Map(document.getElementById('gmaps-canvas'), {
    center,
    zoom: (frm.doc.latitude && frm.doc.longitude) ? 15 : 11,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
  });

  if (frm.doc.latitude && frm.doc.longitude) {
    marker = new google.maps.Marker({ position: center, map, draggable: true });
    marker.addListener('dragend', () => {
      const pos = marker.getPosition();
      update_latlng_fields(frm, pos.lat(), pos.lng());
    });
  }

  map.addListener('click', (e) => {
    place_marker_and_update(frm, e.latLng);
  });

  const input = document.getElementById('gmaps-search');
  autocomplete = new google.maps.places.Autocomplete(input, {
    fields: ['geometry', 'name', 'formatted_address'],
  });
  autocomplete.bindTo('bounds', map);
  autocomplete.addListener('place_changed', () => {
    const place = autocomplete.getPlace();
    if (!place.geometry || !place.geometry.location) return;
    map.panTo(place.geometry.location);
    map.setZoom(16);
    place_marker_and_update(frm, place.geometry.location);
  });

  setTimeout(() => google.maps.event.trigger(map, 'resize'), 300);
}

function place_marker_and_update(frm, latLng) {
  if (!marker) {
    marker = new google.maps.Marker({ position: latLng, map, draggable: true });
    marker.addListener('dragend', () => {
      const pos = marker.getPosition();
      update_latlng_fields(frm, pos.lat(), pos.lng());
    });
  } else {
    marker.setPosition(latLng);
  }
  map.panTo(latLng);
  update_latlng_fields(frm, latLng.lat(), latLng.lng());
}

function update_latlng_fields(frm, lat, lng) {
  frm.set_value('latitude', Number(lat.toFixed(6)));
  frm.set_value('longitude', Number(lng.toFixed(6)));
}

/* ===== Current Location button ===== */
function locate_user(frm) {
  const btn = document.getElementById('btn-locate');
  const restore = set_button_busy(btn, true);

  if (!('geolocation' in navigator)) {
    restore();
    frappe.msgprint(__('Geolocation is not supported by this browser.'));
    return;
  }

  // Requires HTTPS (or localhost)
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude, accuracy } = pos.coords;
      const latLng = new google.maps.LatLng(latitude, longitude);

      place_marker_and_update(frm, latLng);
      map.setZoom(17);

      // Optional: show accuracy circle
      if (accuracyCircle) accuracyCircle.setMap(null);
      accuracyCircle = new google.maps.Circle({
        map,
        center: latLng,
        radius: accuracy || 30,
        fillOpacity: 0.15,
        strokeOpacity: 0.3,
      });

      restore();
      frappe.show_alert({ message: __('Location set from device'), indicator: 'green' });
    },
    (err) => {
      restore();
      const msg =
        err.code === err.PERMISSION_DENIED ? __('Permission denied for location.')
      : err.code === err.POSITION_UNAVAILABLE ? __('Location unavailable.')
      : err.code === err.TIMEOUT ? __('Location request timed out.')
      : __('Failed to get current location.');
      frappe.msgprint(msg);
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

function set_button_busy(btn, busy) {
  const originalText = btn.dataset._label || btn.textContent;
  if (busy) {
    btn.dataset._label = originalText;
    btn.disabled = true;
    btn.textContent = 'Locating…';
    btn.style.opacity = '0.7';
  } else {
    btn.disabled = false;
    btn.textContent = originalText;
    btn.style.opacity = '1';
  }
  return () => set_button_busy(btn, false);
}
