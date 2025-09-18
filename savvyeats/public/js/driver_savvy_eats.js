// Doctype: Driver
frappe.ui.form.on('Driver', {
  onload_post_render: render_driver_coverage_map,
  refresh: render_driver_coverage_map,
});

function render_driver_coverage_map(frm) {
  const fld = frm.fields_dict['zone_map'];
  if (!fld || !fld.$wrapper) return;

  const mapId = 'kc-driver-coverage';
  fld.$wrapper.html(`
    <div style="position:relative">
      <div id="${mapId}" style="
        height:480px; border:1px solid #eef0f3; border-radius:12px; overflow:hidden;
        box-shadow:0 4px 12px rgba(16,24,40,.06);"></div>
      <div id="kc-meta" style="position:absolute; right:12px; top:12px; z-index:2;
        background:#ffffff; border:1px solid #e5e7eb; border-radius:999px; padding:.2rem .6rem; font-size:.78rem;">
        <span id="kc-count">0 pins</span>
      </div>
    </div>
  `);

  // Collect valid pins from child rows
  const pins = (frm.doc.zones || [])
    .map((r, idx) => {
      const lat = parseFloat(r.latitude);
      const lng = parseFloat(r.longitude);
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        return {
          lat, lng,
          title: r.delivery_area || `Pin ${idx+1}`,
          area: r.delivery_area || '',
          name: r.name
        };
      }
      return null;
    })
    .filter(Boolean);

  // Update count pill
  const updateCount = () => {
    const el = document.getElementById('kc-count');
    if (el) el.textContent = `${pins.length} pin${pins.length === 1 ? '' : 's'}`;
  };
  updateCount();

  // No pins? Just render an empty map around Qatar
  if (!pins.length) {
    loadGoogleMaps(() => {
      const map = new google.maps.Map(document.getElementById(mapId), {
        center: { lat: 25.2854, lng: 51.5310 }, // Doha
        zoom: 10,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
      });
      // Optional soft overlay explaining:
      const div = document.createElement('div');
      div.style.cssText = "position:absolute;left:12px;top:12px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:.35rem .5rem;font-size:.8rem;box-shadow:0 2px 8px rgba(16,24,40,.08)";
      div.textContent = 'No delivery pins yet.';
      map.controls[google.maps.ControlPosition.TOP_LEFT].push(div);
    });
    return;
  }

  // Render pins
  loadGoogleMaps(() => {
    const map = new google.maps.Map(document.getElementById(mapId), {
      center: { lat: 25.2854, lng: 51.5310 },
      zoom: 11,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
    });

    const info = new google.maps.InfoWindow();
    const bounds = new google.maps.LatLngBounds();

    // simple colored pin via SVG path (not draggable)
    const svgPin = {
      path: 'M12 2C7.58 2 4 5.58 4 10c0 5.25 8 12 8 12s8-6.75 8-12c0-4.42-3.58-8-8-8zm0 10.25a2.25 2.25 0 1 1 0-4.5 2.25 2.25 0 0 1 0 4.5z',
      fillColor: '#3b82f6',
      fillOpacity: 1,
      strokeWeight: 0,
      scale: 1.4,
      anchor: new google.maps.Point(12, 22),
    };

    pins.forEach(p => {
  const pos = { lat: p.lat, lng: p.lng };

  // 1. Marker (red circle)
  const marker = new google.maps.Marker({
    position: pos,
    map,
    icon: {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 6,
      fillColor: '#ef4444',    // red-500
      fillOpacity: 1,
      strokeColor: '#ffffff',  // white border
      strokeWeight: 2
    },
    clickable: true
  });

  // 2. Range Circle (2 km by default)
  const circle = new google.maps.Circle({
    strokeColor: '#ef4444',
    strokeOpacity: 0.6,
    strokeWeight: 1,
    fillColor: '#ef4444',
    fillOpacity: 0.15,  // light translucent red
    map,
    center: pos,
    radius: 2000 // meters
  });

  // 3. Info Window
  marker.addListener('click', () => {
    const html = `
      <div style="min-width:180px">
        <div style="font-weight:700">${escapeHtml(p.title)}</div>
        <div style="color:#64748b;font-size:.85rem">
          Lat: ${p.lat.toFixed(6)}<br/>
          Lng: ${p.lng.toFixed(6)}
        </div>
      </div>`;
    info.setContent(html);
    info.open(map, marker);
  });

  // 4. Pulse animation
  let grow = true;
  setInterval(() => {
    let s = marker.getIcon().scale;
    if (grow) {
      s += 0.3; if (s > 9) grow = false;
    } else {
      s -= 0.3; if (s < 6) grow = true;
    }
    marker.setIcon({ ...marker.getIcon(), scale: s });
  }, 120);

  bounds.extend(pos);
});


    map.fitBounds(bounds);
    google.maps.event.addListenerOnce(map, 'bounds_changed', () => {
      if (map.getZoom() > 15) map.setZoom(15);
    });
  });
}

/* ---- Utils ---- */
function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const GMAPS_API_KEY = 'AIzaSyDRg_M7g7y3L3wSqPEcteVah14LEcwNIFg';
function loadGoogleMaps(cb) {
  if (window.google && window.google.maps) { cb(); return; }
  if (window.__kc_maps_loading) {
    const t = setInterval(() => {
      if (window.google && window.google.maps) { clearInterval(t); cb(); }
    }, 120);
    return;
  }
  window.__kc_maps_loading = true;
  const s = document.createElement('script');
  s.src = `https://maps.googleapis.com/maps/api/js?key=${GMAPS_API_KEY}`;
  s.async = true; s.defer = true;
  s.onload = () => { window.__kc_maps_loading = false; cb(); };
  s.onerror = () => { window.__kc_maps_loading = false; frappe.msgprint('Failed to load Google Maps.'); };
  document.head.appendChild(s);
}
