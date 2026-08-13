# -*- coding: utf-8 -*-
"""One-shot: extract PRO sections into per-function templates and slim hubs."""
from pathlib import Path

ROOT = Path(r"C:\Users\fabig\proyecto_clima")
TPL = ROOT / "mundo" / "templates"

# (start_marker_substr, end_before_substr) — 1-based inclusive via markers
# We locate by unique substrings then slice.

SECTORS = {
    "agro": {
        "eje": "radiacion",
        "pro_start": "TUCLIMA PRO PANEL",
        "chat": "{% include 'partials/_chat_modal.html' %}",
    },
    "naval": {
        "eje": "ondas",
        "pro_start": "TUCLIMA PRO PANEL",
        "chat": "{% include 'partials/_chat_modal.html' %}",
    },
    "aereo": {
        "eje": "ondas",
        "pro_start": "TUCLIMA PRO PANEL",
        "chat": "{% include 'partials/_chat_modal.html' %}",
    },
    "energia": {
        "eje": "radiacion",
        "pro_start": "TUCLIMA PRO PANEL",
        "chat": "{% include 'partials/_chat_modal.html' %}",
    },
}

TITLES = {
    "operacion": "Operación",
    "radiacion": "Radiación",
    "ondas": "Ondas",
    "climatologia": "Climatología",
    "estadistica": "Estadística",
    "herramientas": "Herramientas",
    "graficos": "Gráficos",
    "didacticas": "Ventanas didácticas",
    "ia": "Chat IA",
}


def find_line(lines, substr, start=0):
    for i in range(start, len(lines)):
        if substr in lines[i]:
            return i
    raise SystemExit(f"Not found: {substr!r}")


def slice_block(lines, start_sub, end_sub, start_from=0):
    a = find_line(lines, start_sub, start_from)
    b = find_line(lines, end_sub, a + 1)
    return a, b, lines[a:b]


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({len(text)} chars)")


BASE = '''{% extends 'base.html' %}
{% block title %}{{ pro_titulo }} · {{ pro_sector|title }} | TuClima{% endblock %}
{% block extra_head %}
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body { background:#020617; color:#e2e8f0; margin:0; font-family:'Segoe UI',system-ui,-apple-system,sans-serif; }
  .tc-pro-page { max-width:960px; margin:0 auto; padding:16px 16px 120px; box-sizing:border-box; }
  .tc-pro-page-head { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:18px; }
  .tc-pro-page-head a.back {
    display:inline-flex; align-items:center; gap:6px; text-decoration:none;
    color:#94a3b8; font-size:0.82rem; font-weight:600; padding:8px 12px; min-height:40px;
    border:1px solid #334155; border-radius:10px; background:rgba(15,23,42,0.85);
  }
  .tc-pro-page-head a.back:hover { color:#67e8f9; border-color:#22d3ee; }
  .tc-pro-page-head h1 { margin:0; font-size:1.15rem; font-weight:800; color:#f1f5f9; letter-spacing:0.02em; }
  .tc-pro-page-head .meta { margin-left:auto; font-size:0.72rem; color:#64748b; }
</style>
{% endblock %}
{% block content %}
{% include 'partials/_nav_secciones.html' with tc_activo=pro_sector %}
{% include 'partials/_menu_pro_interno.html' with sector=pro_sector %}
<div class="tc-pro-page">
  <div class="tc-pro-page-head">
    <a class="back" href="/{{ pro_sector }}/?lat={{ lat }}&lon={{ lon }}">← Panel {{ pro_sector|title }}</a>
    <h1>{{ pro_titulo }}</h1>
    <div class="meta">lat {{ lat|floatformat:3 }} · lon {{ lon|floatformat:3 }}</div>
  </div>
  {% block pro_body %}{% endblock %}
</div>
{% endblock %}
'''

HUB_CARDS = '''{# Hub de funciones PRO — pantallas separadas #}
<div class="tc-pro-hub" style="margin:20px 0 28px;font-family:'Segoe UI',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;flex-wrap:wrap;">
    <div>
      <div style="font-size:0.66rem;letter-spacing:0.12em;color:#64748b;font-weight:700;text-transform:uppercase;">Funciones PRO</div>
      <div style="font-size:0.95rem;color:#e2e8f0;font-weight:700;margin-top:4px;">Elegí una función para abrirla en pantalla completa</div>
    </div>
    <button type="button" onclick="tcToggleProMenu()" style="display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:8px 14px;border-radius:10px;border:1px solid rgba(167,139,250,0.45);background:rgba(167,139,250,0.12);color:#c4b5fd;font-weight:700;font-size:0.82rem;cursor:pointer;font-family:inherit;">Abrir menú</button>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;">
    {% for item in pro_hub_items %}
    <a href="{{ item.href }}" style="text-decoration:none;display:flex;flex-direction:column;gap:6px;padding:14px 14px;min-height:88px;border-radius:14px;border:1px solid {{ item.border }};background:{{ item.bg }};color:{{ item.color }};">
      <span style="font-size:0.72rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;">{{ item.kicker }}</span>
      <span style="font-size:0.95rem;font-weight:800;color:#f8fafc;">{{ item.label }}</span>
      <span style="font-size:0.72rem;color:#94a3b8;line-height:1.35;">{{ item.desc }}</span>
    </a>
    {% endfor %}
  </div>
</div>
{% include 'partials/_menu_pro_interno.html' with sector=pro_sector %}
'''


def hub_items_django(sector, eje):
    # rendered in view; this is just documentation
    pass


def build_funcion_tpl(sector, funcion, body: str) -> str:
    return (
        f"{{% extends 'pro/base_funcion.html' %}}\n"
        f"{{% block pro_body %}}\n"
        f"{body.rstrip()}\n"
        f"{{% endblock %}}\n"
    )


def main():
    write(TPL / "pro" / "base_funcion.html", BASE)
    write(TPL / "partials" / "_hub_pro_funciones.html", HUB_CARDS)

    for sector, meta in SECTORS.items():
        path = TPL / f"{sector}.html"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        eje = meta["eje"]

        # Locate PRO panel wrapper start (comment line) through chat include
        pro_i = find_line(lines, meta["pro_start"])
        # go back to include blank line before comment if possible
        while pro_i > 0 and lines[pro_i - 1].strip() in ("",):
            pro_i -= 1
        # Prefer starting at the HTML comment of PRO PANEL
        for j in range(max(0, pro_i - 5), pro_i + 3):
            if "TUCLIMA PRO PANEL" in lines[j]:
                # include the comment block start `<!--`
                k = j
                while k > 0 and "<!--" not in lines[k]:
                    k -= 1
                pro_i = k
                break

        chat_i = find_line(lines, meta["chat"])

        pro_block = lines[pro_i:chat_i]
        pro_text = "".join(pro_block)

        # Sub-extract within pro_block using relative indices
        def sub(start_sub, end_sub, text=pro_text):
            a = text.find(start_sub)
            if a < 0:
                raise SystemExit(f"{sector}: missing {start_sub!r}")
            b = text.find(end_sub, a + len(start_sub))
            if b < 0:
                raise SystemExit(f"{sector}: missing end {end_sub!r}")
            return text[a:b]

        # operacion: from #pro-operacion through end of timeline (before BOTONES or CALCULADORA)
        # Actually structure: semaforo, botones, timeline, calc...
        # We'll take badge+semaforo+timeline for operacion
        op_parts = []
        if "{% include 'partials/_badge_operabilidad.html' %}" in pro_text:
            op_parts.append("{% include 'partials/_badge_operabilidad.html' %}\n")
        # alert banner if present
        if "alerta_banner.activo" in pro_text:
            # grab the alert if line
            import re
            m = re.search(r"\{% if alerta_banner\.activo %\}.*?\{% endif %\}", pro_text, re.S)
            if m:
                op_parts.append(m.group(0) + "\n")

        # Extract id=pro-operacion div: find start and matching - use next section marker
        a = pro_text.find('id="pro-operacion"')
        if a < 0:
            raise SystemExit(f"{sector}: no pro-operacion")
        # rewind to <div
        a = pro_text.rfind("<div", 0, a)
        # end at BOTONES DE ACCIÓN
        b = pro_text.find("BOTONES DE ACCIÓN", a)
        if b < 0:
            b = pro_text.find('id="pro-herramientas"', a)
        operacion_html = "".join(op_parts) + pro_text[a:b]

        # timeline after herramientas — include in operacion
        t0 = pro_text.find("TIMELINE PRÓXIMAS")
        if t0 > 0:
            t0 = pro_text.rfind("<div", 0, t0)
            # end at CALCULADORA or OJO BIÓNICO
            t1 = pro_text.find("── 4.", t0)
            if t1 < 0:
                t1 = pro_text.find("OJO BIÓNICO", t0)
            if t1 > 0:
                t1 = pro_text.rfind("<!--", t0, t1)
                operacion_html += "\n" + pro_text[t0:t1]

        # herramientas: from pro-herramientas through before estadistica
        h0 = pro_text.find('id="pro-herramientas"')
        h0 = pro_text.rfind("<div", 0, h0)
        h1 = pro_text.find('id="pro-estadistica"')
        # exclude timeline from herramientas by taking botones only + from calc to stats
        # Simpler: from botones through before stats, but remove timeline block
        herramientas_html = pro_text[h0:h1]
        # remove timeline section inside if present
        tl_a = herramientas_html.find("TIMELINE PRÓXIMAS")
        if tl_a >= 0:
            tl_a = herramientas_html.rfind("<!--", 0, tl_a)
            tl_b = herramientas_html.find("── 4.", tl_a)
            if tl_b < 0:
                tl_b = herramientas_html.find("OJO BIÓNICO", tl_a)
            if tl_b > 0:
                tl_b = herramientas_html.rfind("<!--", tl_a, tl_b)
                if tl_b > tl_a:
                    herramientas_html = herramientas_html[:tl_a] + herramientas_html[tl_b:]

        # estadistica
        s0 = pro_text.find('id="pro-estadistica"')
        s0 = pro_text.rfind("<div", 0, s0)
        estadistica_html = pro_text[s0:]

        # Save partials
        part_dir = TPL / "pro" / "partials" / sector
        write(part_dir / "_operacion.html", operacion_html)
        write(part_dir / "_herramientas.html", herramientas_html)
        write(part_dir / "_estadistica.html", estadistica_html)

        # Function pages
        sec_dir = TPL / "pro" / sector
        write(sec_dir / "operacion.html", build_funcion_tpl(sector, "operacion", "{% include 'pro/partials/" + sector + "/_operacion.html' %}"))
        if eje == "radiacion":
            write(sec_dir / "radiacion.html", build_funcion_tpl(sector, "radiacion", "{% include 'partials/_panel_radiacion.html' with sector_radiacion='" + sector + "' %}"))
        else:
            write(sec_dir / "ondas.html", build_funcion_tpl(sector, "ondas", "{% include 'partials/_panel_ondas.html' %}"))
        write(sec_dir / "climatologia.html", build_funcion_tpl(sector, "climatologia", "{% include 'partials/_panel_climatologia.html' %}"))
        write(sec_dir / "estadistica.html", build_funcion_tpl(sector, "estadistica", "{% include 'pro/partials/" + sector + "/_estadistica.html' %}"))
        write(sec_dir / "herramientas.html", build_funcion_tpl(sector, "herramientas", "{% include 'pro/partials/" + sector + "/_herramientas.html' %}"))

        graficos_body = '''
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid rgba(56,189,248,0.25);border-radius:16px;padding:18px;">
  <p style="margin:0 0 10px;color:#94a3b8;font-size:0.85rem;line-height:1.5;">Los gráficos principales del modo viven en el panel general. Desde acá podés ir al monitor operativo o a la estadística avanzada.</p>
  <div style="display:flex;flex-wrap:wrap;gap:10px;">
    <a href="/''' + sector + '''/?lat={{ lat }}&lon={{ lon }}#grafico" style="display:inline-flex;align-items:center;min-height:40px;padding:8px 14px;border-radius:10px;border:1px solid rgba(56,189,248,0.35);color:#67e8f9;text-decoration:none;font-weight:700;font-size:0.82rem;">Ver gráfico del panel</a>
    <a href="/''' + sector + '''/estadistica/?lat={{ lat }}&lon={{ lon }}" style="display:inline-flex;align-items:center;min-height:40px;padding:8px 14px;border-radius:10px;border:1px solid rgba(167,139,250,0.35);color:#c4b5fd;text-decoration:none;font-weight:700;font-size:0.82rem;">Estadística avanzada</a>
  </div>
</div>
'''
        write(sec_dir / "graficos.html", build_funcion_tpl(sector, "graficos", graficos_body))

        didacticas_body = '''
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid rgba(148,163,184,0.25);border-radius:16px;padding:18px;margin-bottom:14px;">
  <p style="margin:0;color:#cbd5e1;font-size:0.9rem;line-height:1.55;">Las ventanas didácticas explican cada instrumento del panel (escalas, riesgos, tip operativo). Abrí el panel general y tocá una tarjeta, o usá el menú PRO para volver.</p>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;">
  <a href="/''' + sector + '''/?lat={{ lat }}&lon={{ lon }}" style="text-decoration:none;padding:14px;border-radius:12px;border:1px solid #334155;background:rgba(15,23,42,0.9);color:#e2e8f0;">
    <div style="font-weight:800;margin-bottom:4px;">Instrumentos</div>
    <div style="font-size:0.75rem;color:#94a3b8;">Tarjetas del panel con ventanas didácticas</div>
  </a>
  <a href="/''' + sector + '''/operacion/?lat={{ lat }}&lon={{ lon }}" style="text-decoration:none;padding:14px;border-radius:12px;border:1px solid #334155;background:rgba(15,23,42,0.9);color:#e2e8f0;">
    <div style="font-weight:800;margin-bottom:4px;">Operación</div>
    <div style="font-size:0.75rem;color:#94a3b8;">Semáforo y tendencia 24h</div>
  </a>
</div>
'''
        write(sec_dir / "didacticas.html", build_funcion_tpl(sector, "didacticas", didacticas_body))

        ia_body = '''
<div style="background:linear-gradient(135deg,#0f172a,#1e1b4b);border:1px solid rgba(167,139,250,0.35);border-radius:16px;padding:18px;margin-bottom:14px;">
  <p style="margin:0 0 12px;color:#cbd5e1;font-size:0.9rem;line-height:1.5;">Chat IA del modo ''' + sector + '''. Se abre el asistente del panel.</p>
  <a href="/''' + sector + '''/?lat={{ lat }}&lon={{ lon }}&open_chat=1" style="display:inline-flex;align-items:center;min-height:42px;padding:10px 16px;border-radius:10px;background:rgba(167,139,250,0.15);border:1px solid rgba(167,139,250,0.45);color:#c4b5fd;text-decoration:none;font-weight:700;">Abrir Chat IA en el panel →</a>
</div>
{% include 'partials/_modal_interactivo.html' %}
'''
        write(sec_dir / "ia.html", build_funcion_tpl(sector, "ia", ia_body))

        # Replace PRO panel in hub with hub cards include
        hub_replace = (
            "<!-- ═══════════════════════════════════════════════════\n"
            "     TUCLIMA PRO · Hub de funciones (pantallas separadas)\n"
            "═══════════════════════════════════════════════════ -->\n"
            "{% include 'partials/_hub_pro_funciones.html' %}\n\n"
        )
        new_lines = lines[:pro_i] + [hub_replace] + lines[chat_i:]
        path.write_text("".join(new_lines), encoding="utf-8")
        print(f"slimmed hub {sector}.html (removed {chat_i - pro_i} lines of inline PRO panel)")


if __name__ == "__main__":
    main()
