<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Container Tracking — Demo</title>

  <!-- Tailwind + Leaflet -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <style>
    #map { height: 360px; }
    .card { @apply bg-white rounded-lg shadow p-4; }
    .kpi { @apply card text-center; }
    .kpi .label { @apply text-xs text-gray-500; }
    .kpi .value { @apply text-2xl font-bold; }
    .table th, .table td { @apply text-sm p-2; }
    .table thead { @apply bg-gray-100; position:sticky; top:0; }
  </style>
</head>

<body class="bg-gray-50 text-gray-900">
  <div class="container mx-auto px-4 py-5">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold">🚢 Container Tracking — Demo</h1>
      <div class="space-x-4 text-sm">
        <a href="/docs.html" class="underline">Docs</a>
        <a href="/test.html" class="underline">Test</a>
      </div>
    </div>

    <!-- Top: Search + KPIs -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Search (full width on small, 1 col on large) -->
      <div class="lg:col-span-2 card flex items-center space-x-2">
        <input id="cn" class="flex-1 border rounded px-3 py-2"
               placeholder="Lookup by Container/Shipment (e.g., MSCU1301003)" />
        <button id="btnSearch" class="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700">Search</button>
      </div>

      <!-- KPI cards (right column) -->
      <div class="grid grid-cols-2 gap-3">
        <div class="kpi"><div class="label">On-Time %</div><div id="kpiOn" class="value">—</div></div>
        <div class="kpi"><div class="label">High Risk</div><div id="kpiHigh" class="value">—</div></div>
        <div class="kpi"><div class="label">Avg Pred Hours</div><div id="kpiAvg" class="value">—</div></div>
        <div class="kpi"><div class="label">Total Shipments</div><div id="kpiTotal" class="value">—</div></div>
      </div>
    </div>

    <!-- Middle: Map (left) + Table (right) -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
      <!-- Map -->
      <div class="lg:col-span-2 card">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold">🗺️ Map</h3>
        </div>
        <div id="map" class="rounded border"></div>
      </div>

      <!-- Shipments table -->
      <div class="card">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold">📦 Shipments</h3>
          <input id="flt" class="border rounded px-2 py-1 text-sm" placeholder="Search vessel / container..." />
        </div>
        <div style="max-height:360px;overflow:auto">
          <table class="w-full table">
            <thead>
              <tr>
                <th class="text-left">ID</th>
                <th class="text-left">Vessel</th>
                <th class="text-left">Lat</th>
                <th class="text-left">Lon</th>
                <th class="text-left">Waypoint</th>
                <th class="text-left">Pred Hours</th>
                <th class="text-left">ETA (UTC)</th>
                <th class="text-left">Risk</th>
              </tr>
            </thead>
            <tbody id="rows"></tbody>
          </table>
        </div>
        <p class="text-xs text-gray-500 mt-2">Click a row to zoom & load weather.</p>
      </div>
    </div>

    <!-- Bottom: Weather + Summary + Details -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
      <!-- Weather -->
      <div class="card">
        <h3 class="font-semibold mb-2">🌦️ Weather</h3>
        <div id="weather" class="text-sm text-gray-700">—</div>
      </div>

      <!-- Summary -->
      <div class="card">
        <h3 class="font-semibold mb-2">🧠 Summary</h3>
        <textarea id="summary" rows="6" class="w-full border rounded p-3 text-sm"
                  placeholder="Per-container summary will appear here"></textarea>
        <div class="mt-2">
          <button id="btnGen" class="px-3 py-2 rounded bg-indigo-600 text-white hover:bg-indigo-700">Generate</button>
        </div>
      </div>

      <!-- Details -->
      <div class="card">
        <h3 class="font-semibold mb-2">📋 Details</h3>
        <div id="details" class="text-sm text-gray-700">—</div>
      </div>
    </div>
  </div>

  <script>
    let map, markers=[], lines=[], allItems=[], currentItem=null;

    // ----- Map helpers -----
    function initMap() {
      map = L.map('map').setView([20, 0], 2);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
    }
    function clearMap(){ markers.forEach(m=>m.remove()); lines.forEach(l=>l.remove()); markers=[]; lines=[]; }
    function renderMap(it){
      clearMap();
      const m1 = L.marker([it.lat, it.lon]).addTo(map).bindPopup(`${it.vessel}<br>${it.id}`).openPopup();
      const m2 = L.circleMarker([it.waypoint.lat, it.waypoint.lon], { radius:6 }).addTo(map).bindPopup('Next waypoint');
      const l  = L.polyline([[it.lat,it.lon],[it.waypoint.lat,it.waypoint.lon]], { color:'#0b5', weight:2, dashArray:'6,6' }).addTo(map);
      markers.push(m1,m2); lines.push(l);
      map.fitBounds([[it.lat,it.lon],[it.waypoint.lat,it.waypoint.lon]], { padding:[40,40] });
    }

    // ----- KPI helpers -----
    function setText(id, v){ document.getElementById(id).textContent = v; }
    function renderFleetKpis(items){
      const n = items.length || 1;
      const on = items.filter(i=>i.metrics.onTime).length;
      const high = items.filter(i=>i.metrics.risk==='HIGH').length;
      const avg = items.reduce((a,c)=>a+c.metrics.predHours,0)/n;
      setText('kpiOn',   Math.round(on/n*100) + '%');
      setText('kpiHigh', String(high));
      setText('kpiAvg',  avg.toFixed(1));
      setText('kpiTotal', String(items.length));
    }

    // ----- Table -----
    function renderTable(items) {
      const tbody = document.getElementById('rows');
      tbody.innerHTML = '';
      items.forEach(it => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50 cursor-pointer';
        tr.innerHTML = `
          <td class="font-mono">${it.id}</td>
          <td>${it.vessel}</td>
          <td>${it.lat.toFixed(3)}</td>
          <td>${it.lon.toFixed(3)}</td>
          <td>${it.waypoint.lat.toFixed(2)}, ${it.waypoint.lon.toFixed(2)}</td>
          <td>${it.metrics.predHours.toFixed(1)}</td>
          <td>${it.metrics.etaUtc}</td>
          <td class="${it.metrics.risk==='HIGH'?'text-red-600 font-semibold':''}">${it.metrics.risk}</td>
        `;
        tr.addEventListener('click',()=>selectItem(it));
        tbody.appendChild(tr);
      });
    }

    // ----- Weather -----
    async function loadWeather(lat, lon){
      const box = document.getElementById('weather');
      box.textContent = 'Loading...';
      try{
        const r = await fetch(`/api/weather?lat=${lat}&lon=${lon}`);
        const j = await r.json();
        const c = j.current || {};
        box.innerHTML =
          `Temp: <b>${c.temperature_2m ?? '-'}</b>°C &nbsp; ` +
          `Feels: <b>${c.apparent_temperature ?? '-'}</b>°C &nbsp; ` +
          `Humidity: <b>${c.relative_humidity_2m ?? '-'}</b>% &nbsp; ` +
          `Wind: <b>${c.wind_speed_10m ?? '-'}</b> m/s &nbsp; ` +
          `Code: <b>${c.weather_code ?? '-'}</b>`;
      }catch(e){
        box.innerHTML = '<span class="text-red-600">Weather unavailable</span>';
      }
    }

    // ----- Details -----
    function renderDetails(it){
      const m = it.metrics;
      document.getElementById('details').innerHTML = `
        <div><span class="text-gray-500">Vessel</span><br><b>${it.vessel}</b></div>
        <div class="mt-2"><span class="text-gray-500">Shipment</span><br><code>${it.id}</code></div>
        <div class="mt-2"><span class="text-gray-500">ETA (UTC)</span><br>${m.etaUtc}</div>
        <div class="mt-2"><span class="text-gray-500">Planned Hours</span><br>${it.etaPlannedHrs}</div>
      `;
    }

    // ----- Selection -----
    async function selectItem(it){
      currentItem = it;
      renderMap(it);
      renderDetails(it);
      await loadWeather(it.lat, it.lon);
      // Also fetch per-container summary (uses first container as identifier)
      try{
        const cn = it.containers[0] || it.id;
        const s  = await fetch('/api/summary?cn=' + encodeURIComponent(cn), { method: 'POST' });
        const sj = await s.json();
        document.getElementById('summary').value = sj.summary || '';
      }catch(_){}
    }

    // ----- Search -----
    async function lookup(){
      const q = document.getElementById('cn').value.trim();
      if(!q) return alert('Enter a container or shipment id');
      const details = document.getElementById('details');
      details.textContent = 'Searching...';
      try{
        const r = await fetch('/api/container?cn=' + encodeURIComponent(q));
        if(!r.ok){
          const err = await r.json().catch(()=>({error:'Not found'}));
          const sug = err.suggestions || [];
          const msg = (err.error || 'Not found') + (sug.length ? '<br><b>Suggestions:</b><br>' +
            sug.map(s => typeof s === 'string' ? s : `${s.sample} (${s.vessel})`).join('<br>') : '');
          details.innerHTML = `<span class="text-red-600">${msg}</span>`;
          return;
        }
        const j = await r.json();
        await selectItem(j.item);
        if (j.summary) document.getElementById('summary').value = j.summary; // use API-provided summary
      }catch(e){
        details.innerHTML = `<span class="text-red-600">${e.message}</span>`;
      }
    }

    // ----- Generate button (per-container) -----
    async function gen(){
      const cn = document.getElementById('cn').value.trim();
      if(!cn) return alert('Enter a container first.');
      const r = await fetch('/api/summary?cn=' + encodeURIComponent(cn), { method:'POST' });
      const j = await r.json();
      document.getElementById('summary').value = j.summary || '';
    }

    // ----- Boot -----
    async function boot(){
      initMap();
      try{
        const r = await fetch('/api/ships'); const j = await r.json();
        allItems = j.items || [];
        renderFleetKpis(allItems);
        renderTable(allItems);
        if(allItems.length) selectItem(allItems[0]);
      }catch(e){ console.error(e); }
      document.getElementById('btnSearch').onclick = lookup;
      document.getElementById('btnGen').onclick = gen;
      document.getElementById('cn').addEventListener('keydown', e => { if(e.key==='Enter') lookup(); });
      document.getElementById('flt').addEventListener('input', () => {
        const v = document.getElementById('flt').value.toLowerCase();
        const f = allItems.filter(it =>
          it.id.toLowerCase().includes(v) ||
          it.vessel.toLowerCase().includes(v) ||
          it.containers.some(c => c.toLowerCase().includes(v))
        );
        renderTable(f);
      });
    }
    boot();
  </script>
</body>
</html>
