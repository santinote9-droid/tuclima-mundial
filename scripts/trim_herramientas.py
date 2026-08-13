from pathlib import Path

root = Path(r"C:\Users\fabig\proyecto_clima\mundo\templates\pro\partials")
for sector in ["agro", "naval", "aereo", "energia"]:
    p = root / sector / "_herramientas.html"
    t = p.read_text(encoding="utf-8")
    cut_at = None
    for marker in ["ESTADÍSTICA CLIMÁTICA", 'id="pro-estadistica"']:
        i = t.find(marker)
        if i >= 0:
            cut_at = t.rfind("\n", 0, i)
            if cut_at < 0:
                cut_at = i
            break
    if cut_at is not None:
        t = t[:cut_at]
    p.write_text(t.rstrip() + "\n", encoding="utf-8")
    print(sector, "ok", len(t))
