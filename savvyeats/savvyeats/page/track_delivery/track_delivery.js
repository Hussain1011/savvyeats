// Page: Track Delivery
// Server API:
// - savvyeats.savvyeats.page.track_delivery.track_delivery.get_delivery_tracking(date_str)
// - savvyeats.savvyeats.page.track_delivery.track_delivery.get_single_trip(trip_name)
// - savvyeats.savvyeats.page.track_delivery.track_delivery.get_trip_locations_since(trip_name, since_ts)

frappe.pages['track-delivery'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Track Delivery',
    single_column: true
  });

  $(wrapper).find('.layout-main-section').html(`
    <style>
      .td-shell { display:grid; grid-template-columns: 320px 1fr; gap:16px; }
      .td-card { border:1px solid #e5e7eb; border-radius:12px; background:#fff; box-shadow:0 6px 18px rgba(16,24,40,.06); }
      .td-trip { padding:12px; border-bottom:1px dashed #eef2f7; cursor:pointer; }
      .td-trip:hover { background:#fafafc; }
      .td-pill { display:inline-flex; align-items:center; gap:6px; padding:2px 8px; border-radius:999px; font-size:11px; border:1px solid #e5e7eb; background:#f8fafc; }
      .td-grid { display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; }
      .td-stat { padding:12px; border-radius:12px; text-align:center; }
      .td-stat h3 { margin:4px 0 0; font-size:22px; }
      .td-stat small { color:#64748b; text-transform:uppercase; letter-spacing:.06em; }
      .td-stat--green { background:#ecfdf5; border:1px solid #a7f3d0; }
      .td-stat--orange{ background:#fff7ed; border:1px solid #fed7aa; }
      .td-stat--red   { background:#fef2f2; border:1px solid #fecaca; }
      .td-meta { display:flex; justify-content:space-between; align-items:center; gap:8px; }
      .td-badge { background:#eef2ff; border:1px solid #c7d2fe; border-radius:999px; padding:2px 8px; font-size:11px; }
      .td-map { height:560px; border-radius:12px; overflow:hidden; }
      .td-empty { padding:24px; color:#64748b; text-align:center; }
      .td-legend { display:flex; gap:8px; align-items:center; }
      .td-dot{ width:10px;height:10px;border-radius:50%; display:inline-block; }
      @media (max-width: 1024px) { .td-shell { grid-template-columns: 1fr; } }
    </style>

    <div class="td-shell">
      <div class="td-card" id="td-left">
        <div style="padding:12px; position:sticky; top:0; background:#fff; border-bottom:1px solid #eef0f3; z-index:1;">
          <div id="td-filter"></div>
        </div>
        <div id="td-trip-list"></div>
      </div>

      <div class="td-card" id="td-right">
        <div style="padding:12px; border-bottom:1px solid #eef0f3;">
          <div class="td-meta">
            <div>
              <div id="td-title" style="font-weight:700; font-size:16px;">Select a trip</div>
              <div id="td-sub" class="text-muted" style="font-size:12px;"></div>
            </div>
            <div style="display:flex; gap:8px; align-items:center;">
              <button class="btn btn-xs btn-default" id="td-refresh-trip">Refresh Trip</button>
              <button class="btn btn-xs btn-default" id="td-live-toggle">Live: On</button>
              <div class="td-legend">
                <span class="td-pill"><span class="td-dot" style="background:#22c55e"></span>Visited</span>
                <span class="td-pill"><span class="td-dot" style="background:#f59e0b"></span>In Process</span>
                <span class="td-pill"><span class="td-dot" style="background:#ef4444"></span>Pending</span>
              </div>
            </div>
          </div>
        </div>
        <div style="padding:12px;">
          <div class="td-grid">
            <div class="td-stat td-stat--green"><small>Delivered</small><h3 id="s-delivered">0</h3></div>
            <div class="td-stat td-stat--orange"><small>In Process</small><h3 id="s-inproc">0</h3></div>
            <div class="td-stat td-stat--red"><small>Pending</small><h3 id="s-pending">0</h3></div>
          </div>
          <div class="td-map td-card" id="td-map" style="margin-top:12px;"></div>
        </div>
      </div>
    </div>
  `);

  // ------- Date filter -------
  const df = new frappe.ui.FieldGroup({
    fields: [{ fieldtype: "Date", fieldname: "date", label: "Date", reqd: 1, default: frappe.datetime.now_date() }],
    body: $('#td-filter'),
  });
  df.make();

  // ------- State -------
  let _currentTripName = null;
  let _live = {
    timer: null,
    lastTs: null,
    enabled: true,
    map: null,
    polyline: null,
    truck: null
  };

  // ------- Load trips for date -------
  function loadTrips() {
    const date = df.get_value('date');
    if (!date) return;

    frappe.call({
      method: "savvyeats.savvyeats.page.track_delivery.track_delivery.get_delivery_tracking",
      args: { date_str: date },
      freeze: true,
      callback: r => {
        const trips = (r.message && r.message.trips) || [];
        renderTripList(trips);
        clearRight();
      }
    });
  }
  df.fields_dict.date.df.onchange = loadTrips;
  loadTrips();

  // ------- Left: trip list -------
  function renderTripList(trips) {
    const $list = $('#td-trip-list').empty();
    if (!trips.length) {
      $list.html(`<div class="td-empty">No trips for this date.</div>`);
      return;
    }
    trips.forEach(t => {
      const trip = t.trip, c = t.counts;
      const title = `${trip.driver_name || trip.driver} · ${trip.delivery_time_slot || 'All Day'}`;
      const sub = frappe.datetime.user_to_str(trip.departure_time);

      const $row = $(`
        <div class="td-trip" data-trip="${frappe.utils.escape_html(trip.name)}">
          <div style="font-weight:600">${frappe.utils.escape_html(title)}</div>
          <div class="text-muted" style="font-size:12px;">${frappe.utils.escape_html(sub)}</div>
          <div style="margin-top:6px; display:flex; gap:6px;">
            <span class="td-badge">✔ ${c.delivered}</span>
            <span class="td-badge">● ${c.in_process}</span>
            <span class="td-badge">⏳ ${c.pending}</span>
          </div>
        </div>
      `);
      $row.on('click', () => showTrip(t));
      $list.append($row);
    });
  }

  // ------- Right: reset -------
  function clearRight() {
    stopLivePolling();
    _currentTripName = null;
    _live = { timer: null, lastTs: null, enabled: true, map: null, polyline: null, truck: null };
    $('#td-title').text('Select a trip');
    $('#td-sub').text('');
    $('#s-delivered').text(0);
    $('#s-inproc').text(0);
    $('#s-pending').text(0);
    $('#td-live-toggle').text('Live: On');
    ensureGoogle(() => {
      new google.maps.Map(document.getElementById('td-map'), {
        center: { lat: 25.2854, lng: 51.5310 }, zoom: 10, mapTypeControl: false, streetViewControl: false
      });
    });
  }

  // ------- Show trip (summary + map + live init) -------
  function showTrip(tdata) {
    const trip = tdata.trip, stops = tdata.stops || [], locs = tdata.locations || [], c = tdata.counts || {};
    _currentTripName = trip.name;

    $('#td-title').text(`${trip.driver_name || trip.driver} · ${trip.delivery_time_slot || 'All Day'}`);
    const totalMeters = trip.total_distance || 0;
    const totalStr = totalMeters >= 1000 ? `${(totalMeters / 1000).toFixed(1)} km` : `${Math.round(totalMeters)} m`;
    $('#td-sub').text(`${frappe.datetime.user_to_str(trip.departure_time)} · ${stops.length} stops · ${totalStr}`);

    $('#s-delivered').text(c.delivered || 0);
    $('#s-inproc').text(c.in_process || 0);
    $('#s-pending').text(c.pending || 0);

    ensureGoogle(() => {
      renderTripMap(trip, stops, locs);
      _live.lastTs = (locs && locs.length) ? locs[locs.length - 1].timestamp : null;
      if (_live.enabled) startLivePolling();
    });
  }

  // ------- Header buttons -------
  $('#td-refresh-trip').on('click', () => {
    if (!_currentTripName) return;
    frappe.call({
      method: "savvyeats.savvyeats.page.track_delivery.track_delivery.get_single_trip",
      args: { trip_name: _currentTripName },
      freeze: true
    }).then(r => { if (r.message) showTrip(r.message); });
  });

  $('#td-live-toggle').on('click', () => {
    _live.enabled = !_live.enabled;
    $('#td-live-toggle').text(_live.enabled ? 'Live: On' : 'Live: Off');
    if (_live.enabled) startLivePolling(); else stopLivePolling();
  });

  // ------- Map render (with Directions API routes) -------
  function renderTripMap(trip, stops, locs) {
    stopLivePolling();

    const map = new google.maps.Map(document.getElementById('td-map'), {
      center: { lat: 25.2854, lng: 51.5310 },
      zoom: 12,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true
    });

    _live.map = map;

    const bounds = new google.maps.LatLngBounds();
    const info = new google.maps.InfoWindow();

    // Sort by sequence (idx)
    const ordered = (stops || []).slice().sort((a, b) => (a.idx || 0) - (b.idx || 0));

    // START marker
    let startPt = null;
    if (trip.start_latitude && trip.start_longitude) {
      startPt = { lat: parseFloat(trip.start_latitude), lng: parseFloat(trip.start_longitude) };
      new google.maps.Marker({
        position: startPt, map,
        icon: { path: google.maps.SymbolPath.CIRCLE, scale: 7, fillColor: '#2563eb', fillOpacity: 1, strokeColor: '#ffffff', strokeWeight: 2 },
        title: 'Start'
      });
      bounds.extend(startPt);
    }

    // STOP markers (numbered & colored)
    ordered.forEach((s, i) => {
      const lat = parseFloat(s.latitude), lng = parseFloat(s.longitude);
      if (!isFinite(lat) || !isFinite(lng)) return;

      const visited = !!(s.visited);
      const locked  = !visited && !!(s.locked);
      const color   = visited ? '#22c55e' : (locked ? '#f59e0b' : '#ef4444');

      const m = new google.maps.Marker({
        position: { lat, lng }, map,
        icon: circleIcon(color),
        label: { text: String(i + 1), color: '#ffffff', fontSize: '10px', fontWeight: '700' },
        title: `${s.customer_name || s.customer || ''}`
      });

      m.addListener('click', () => {
        const distMeters = s.distance || 0;
        const distStr = distMeters >= 1000 ? `${(distMeters/1000).toFixed(1)} km` : `${Math.round(distMeters)} m`;
        info.setContent(`
          <div style="min-width:220px">
            <div style="font-weight:700">${frappe.utils.escape_html(s.customer_name || s.customer || 'Stop')}</div>
            <div style="color:#64748b;font-size:12px">${frappe.utils.escape_html(s.address || '')}</div>
            <div style="margin-top:6px;font-size:12px">
              Seq: <b>${s.idx || i + 1}</b> · Status: <b>${visited ? 'Visited' : (locked ? 'In Process' : 'Pending')}</b><br/>
              Distance: <b>${distStr}</b>
            </div>
          </div>
        `);
        info.open({ anchor: m, map });
      });

      bounds.extend(m.getPosition());
    });

    // ---- PLANNED ROUTE via Directions API ----
    const dirSvc = new google.maps.DirectionsService();
    const lastVisitedIdx = [...ordered].map(s => !!s.visited).lastIndexOf(true);
    const inProcIdx = ordered.findIndex(s => !s.visited && !!s.locked);
    const toLL = s => (s && isFinite(+s.latitude) && isFinite(+s.longitude))
      ? new google.maps.LatLng(parseFloat(s.latitude), parseFloat(s.longitude)) : null;

    // Completed chain (grey)
    if ((lastVisitedIdx >= 0) && (startPt || toLL(ordered[0]))) {
      const origin = startPt ? new google.maps.LatLng(startPt.lat, startPt.lng) : toLL(ordered[0]);
      const dest   = toLL(ordered[lastVisitedIdx]);
      const waypoints = [];
      for (let i = 0; i < lastVisitedIdx; i++) {
        const ll = toLL(ordered[i]);
        if (ll) waypoints.push({ location: ll, stopover: false });
      }
      drawRoute(dirSvc, map, origin, dest, { color: '#9ca3af', dashed: false, zIndex: 20, waypoints });
    }

    // In-process leg (orange)
    if (inProcIdx >= 0) {
      const anchor = (lastVisitedIdx >= 0 ? toLL(ordered[lastVisitedIdx])
                    : (startPt ? new google.maps.LatLng(startPt.lat, startPt.lng) : toLL(ordered[0])));
      const dest = toLL(ordered[inProcIdx]);
      if (anchor && dest) drawRoute(dirSvc, map, anchor, dest, { color: '#f59e0b', dashed: false, zIndex: 30 });
    }

    // Remaining pending chain (yellow dashed)
    let startAnchor = null;
    if (inProcIdx >= 0) startAnchor = toLL(ordered[inProcIdx]);
    else if (lastVisitedIdx >= 0) startAnchor = toLL(ordered[lastVisitedIdx]);
    else startAnchor = startPt ? new google.maps.LatLng(startPt.lat, startPt.lng) : toLL(ordered[0]);

    if (startAnchor) {
      const pending = ordered.filter((s, i) => i > Math.max(inProcIdx, lastVisitedIdx));
      if (pending.length === 1) {
        const dest = toLL(pending[0]);
        if (dest) drawRoute(dirSvc, map, startAnchor, dest, { color: '#facc15', dashed: true, zIndex: 10 });
      } else if (pending.length > 1) {
        const dest = toLL(pending[pending.length - 1]);
        const waypoints = pending.slice(0, -1).map(s => ({ location: toLL(s), stopover: false })).filter(w => !!w.location);
        if (dest) drawRoute(dirSvc, map, startAnchor, dest, { color: '#facc15', dashed: true, zIndex: 10, waypoints });
      }
    }

    // ---- LIVE ROUTE (Driver Location) ----
    const livePath = (locs || [])
      .map(l => ({ lat: parseFloat(l.latitude), lng: parseFloat(l.longitude), ts: l.timestamp }))
      .filter(pt => isFinite(pt.lat) && isFinite(pt.lng));

    const allVisited = ordered.length && ordered.every(s => !!s.visited);
    _live.polyline = new google.maps.Polyline({
      map, path: livePath,
      strokeColor: allVisited ? '#9ca3af' : '#f59e0b',
      strokeOpacity: 0.9, strokeWeight: 3
    });

    if (livePath.length) {
      const last = livePath[livePath.length - 1];
      _live.truck = new google.maps.Marker({
        position: last, map, title: 'Current Position',
        icon: truckIcon(allVisited ? '#9ca3af' : '#f59e0b')
      });
      // pulse
      let grow = true;
      const pulse = setInterval(() => {
        if (!_live.truck) return clearInterval(pulse);
        const ic = _live.truck.getIcon();
        const base = ic.scale || 7;
        const s = grow ? Math.min(9, base + 0.3) : Math.max(7, base - 0.3);
        grow = (s >= 9) ? false : (s <= 7) ? true : grow;
        _live.truck.setIcon({ ...ic, scale: s });
      }, 120);
      bounds.extend(last);
    }

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds);
      google.maps.event.addListenerOnce(map, 'bounds_changed', () => { if (map.getZoom() > 16) map.setZoom(16); });
    }
  }

  // ------- Live polling (only route/position) -------
  const POLL_MS = 8000;

  function startLivePolling() {
    stopLivePolling();
    if (!_currentTripName || !_live.enabled) return;

    if (document.hidden) { _live.timer = setTimeout(startLivePolling, POLL_MS); return; }

    frappe.call({
      method: "savvyeats.savvyeats.page.track_delivery.track_delivery.get_trip_locations_since",
      args: { trip_name: _currentTripName, since_ts: _live.lastTs },
    }).then(r => {
      const locs = (r.message && r.message.locations) || [];
      const lastTs = r.message && r.message.last_ts;

      if (_live.map && _live.polyline && locs.length) {
        const append = locs.map(l => ({ lat: parseFloat(l.latitude), lng: parseFloat(l.longitude) }))
                           .filter(pt => isFinite(pt.lat) && isFinite(pt.lng));
        if (append.length) {
          const path = _live.polyline.getPath();
          append.forEach(pt => path.push(pt));

          const last = append[append.length - 1];
          if (_live.truck) _live.truck.setPosition(last);
          else {
            _live.truck = new google.maps.Marker({
              position: last, map: _live.map, title: 'Current Position',
              icon: truckIcon('#f59e0b')
            });
          }
        }
      }
      if (lastTs) _live.lastTs = lastTs;
      _live.timer = setTimeout(startLivePolling, POLL_MS);
    }).catch(() => { _live.timer = setTimeout(startLivePolling, POLL_MS); });
  }

  function stopLivePolling() { if (_live.timer) { clearTimeout(_live.timer); _live.timer = null; } }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopLivePolling();
    else if (_live.enabled && _currentTripName) startLivePolling();
  });

  // ------- Helpers -------
  function circleIcon(fill) {
    return { path: google.maps.SymbolPath.CIRCLE, scale: 9, fillColor: fill, fillOpacity: 1, strokeColor: '#ffffff', strokeWeight: 2 };
  }
  function truckIcon(fill) {
    return { path: google.maps.SymbolPath.CIRCLE, scale: 7, fillColor: fill, fillOpacity: 1, strokeColor: '#ffffff', strokeWeight: 2 };
  }
  function drawRoute(dirSvc, map, origin, dest, opts) {
    const req = {
      origin, destination: dest,
      waypoints: opts.waypoints || undefined,
      travelMode: google.maps.TravelMode.DRIVING,
      optimizeWaypoints: false,
      provideRouteAlternatives: false
    };
    dirSvc.route(req, (res, status) => {
      if (status !== google.maps.DirectionsStatus.OK || !res || !res.routes || !res.routes.length) return;
      const renderer = new google.maps.DirectionsRenderer({
        map, preserveViewport: true, suppressMarkers: true,
        polylineOptions: polylineStyle(opts.color || '#0ea5e9', opts.dashed, opts.zIndex || 1)
      });
      renderer.setDirections(res);
    });
  }
  function polylineStyle(color, dashed, zIndex) {
    return {
      strokeColor: color, strokeOpacity: 1, strokeWeight: 4, zIndex: zIndex || 1,
      icons: dashed ? [{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, scale: 3 }, offset: '0', repeat: '12px' }] : null
    };
  }

  // ------- Google loader -------
  const GMAPS_API_KEY = 'AIzaSyBPPNWFZnZobn7qSzM7tF1mxshuvEVbBJg';
  function ensureGoogle(cb) {
    if (window.google && window.google.maps) return cb();
    if (window.__td_maps_loading) {
      const t = setInterval(() => { if (window.google && window.google.maps) { clearInterval(t); cb(); } }, 150);
      return;
    }
    window.__td_maps_loading = true;
    const s = document.createElement('script');
    s.src = `https://maps.googleapis.com/maps/api/js?key=${GMAPS_API_KEY}`;
    s.async = true; s.defer = true;
    s.onload = () => { window.__td_maps_loading = false; cb(); };
    s.onerror = () => { window.__td_maps_loading = false; frappe.msgprint('Failed to load Google Maps.'); };
    document.head.appendChild(s);
  }
};
