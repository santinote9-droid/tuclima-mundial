from pathlib import Path

root = Path(r"C:\Users\fabig\proyecto_clima\mundo\templates\pro\partials")
old_tabs = 'style="display:flex; gap:6px; padding:12px 20px 0; overflow-x:auto;"'
new_tabs = 'class="tc-stats-tabs"'
old_scroll = (
    'style="display:flex; gap:8px; overflow-x:auto; padding-bottom:6px; '
    'scrollbar-width:thin; scrollbar-color:rgba(51,65,85,0.5) transparent;"'
)
new_scroll = 'class="tc-scroll-x" style="display:flex; gap:8px;"'

for sector in ["agro", "aereo", "energia", "naval"]:
    p = root / sector / "_estadistica.html"
    t = p.read_text(encoding="utf-8")
    if old_tabs in t:
        t = t.replace(old_tabs, new_tabs, 1)
        p.write_text(t, encoding="utf-8")
        print(sector, "tabs ok")
    elif "tc-stats-tabs" in t:
        print(sector, "tabs already")
    else:
        print(sector, "tabs MISSING")

    p = root / sector / "_operacion.html"
    t = p.read_text(encoding="utf-8")
    if old_scroll in t:
        t = t.replace(old_scroll, new_scroll)
        p.write_text(t, encoding="utf-8")
        print(sector, "scroll ok")
    else:
        print(sector, "scroll skip")
