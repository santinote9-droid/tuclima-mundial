/**
 * TuClima embeddable weather widget
 *
 * Usage:
 * <div id="tuclima-widget"
 *      data-lat="-34.60"
 *      data-lon="-58.38"
 *      data-key="YOUR_API_KEY"
 *      data-base="https://tu-dominio.onrender.com"></div>
 * <script src="https://tu-dominio.onrender.com/static/js/widget.js" async></script>
 */
(function () {
  'use strict';

  function el(tag, style, text) {
    var n = document.createElement(tag);
    if (style) n.setAttribute('style', style);
    if (text != null) n.textContent = text;
    return n;
  }

  function mount(root) {
    var lat = root.getAttribute('data-lat');
    var lon = root.getAttribute('data-lon');
    var key = root.getAttribute('data-key') || '';
    var base = (root.getAttribute('data-base') || '').replace(/\/$/, '');
    var sector = root.getAttribute('data-sector') || '';
    if (!lat || !lon || !base) {
      root.textContent = 'TuClima widget: faltan data-lat, data-lon o data-base';
      return;
    }

    root.innerHTML = '';
    var card = el('div',
      'font-family:Segoe UI,system-ui,sans-serif;background:#0f172a;color:#e2e8f0;' +
      'border:1px solid #334155;border-radius:12px;padding:14px 16px;max-width:280px;' +
      'box-sizing:border-box;line-height:1.35;');
    var title = el('div', 'font-size:11px;letter-spacing:.08em;color:#64748b;font-weight:700;text-transform:uppercase;', 'TuClima');
    var body = el('div', 'margin-top:8px;font-size:13px;color:#94a3b8;', 'Cargando…');
    var foot = el('a',
      'display:inline-block;margin-top:10px;font-size:11px;color:#38bdf8;text-decoration:none;',
      'Powered by TuClima');
    foot.href = base + '/?lat=' + encodeURIComponent(lat) + '&lon=' + encodeURIComponent(lon);
    foot.target = '_blank';
    foot.rel = 'noopener';
    card.appendChild(title);
    card.appendChild(body);
    card.appendChild(foot);
    root.appendChild(card);

    var url = base + '/api/v1/widget/?lat=' + encodeURIComponent(lat) + '&lon=' + encodeURIComponent(lon);
    if (sector) url += '&sector=' + encodeURIComponent(sector);
    if (key) url += '&api_key=' + encodeURIComponent(key);

    var headers = { 'Accept': 'application/json' };
    if (key) headers['Authorization'] = 'Bearer ' + key;

    fetch(url, { headers: headers, credentials: key ? 'omit' : 'same-origin' })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok || !res.j.ok) {
          body.textContent = (res.j && res.j.error) || 'Error al cargar clima';
          body.style.color = '#f87171';
          return;
        }
        var d = res.j;
        body.innerHTML = '';
        var temp = el('div', 'font-size:28px;font-weight:800;color:#f8fafc;',
          (d.temp_c != null ? Math.round(d.temp_c) + '°C' : '—'));
        var meta = el('div', 'margin-top:6px;font-size:12px;color:#94a3b8;',
          'Viento ' + (d.viento_kmh != null ? Math.round(d.viento_kmh) + ' km/h' : '—') +
          ' · Humedad ' + (d.humedad_pct != null ? Math.round(d.humedad_pct) + '%' : '—'));
        var rango = el('div', 'margin-top:4px;font-size:12px;color:#64748b;',
          'Máx ' + (d.tmax_c != null ? Math.round(d.tmax_c) + '°' : '—') +
          ' / Mín ' + (d.tmin_c != null ? Math.round(d.tmin_c) + '°' : '—'));
        body.appendChild(temp);
        body.appendChild(meta);
        body.appendChild(rango);
        if (d.operabilidad) {
          var op = el('div',
            'margin-top:8px;padding:6px 8px;border-radius:8px;font-size:11px;font-weight:700;' +
            'border:1px solid ' + d.operabilidad.color + '55;color:' + d.operabilidad.color + ';' +
            'background:' + d.operabilidad.color + '18;',
            d.operabilidad.label + ' — ' + d.operabilidad.resumen);
          body.appendChild(op);
        }
      })
      .catch(function () {
        body.textContent = 'No se pudo conectar con TuClima';
        body.style.color = '#f87171';
      });
  }

  function boot() {
    var nodes = document.querySelectorAll('#tuclima-widget, [data-tuclima-widget]');
    for (var i = 0; i < nodes.length; i++) mount(nodes[i]);
  }

  window.TuClimaWidget = { boot: boot, mount: mount };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
