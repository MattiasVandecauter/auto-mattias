"""Render gevonden autos naar een interactief, self-contained HTML-rapport."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .models import Car

TEMPLATE = Path(__file__).parent / "templates" / "report.html"


def _embed(payload: str) -> str:
    return payload.replace("</", "<\\/")


def _replace_script(html: str, script_id: str, payload: str) -> str:
    pattern = re.compile(r'(<script id="' + re.escape(script_id) + r'"[^>]*>).*?(</script>)', re.S)
    return pattern.sub(lambda m: m.group(1) + "\n" + payload + "\n" + m.group(2), html, count=1)


def render(cars, out_path, *, title: str = "EV-occasies", subtitle: str = "") -> Path:
    rows = [c.to_dict() if isinstance(c, Car) else dict(c) for c in cars]
    meta = {
        "title": title,
        "subtitle": subtitle,
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "count": len(rows),
        "sources": sorted({r.get("source") for r in rows if r.get("source")}),
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    html = _replace_script(html, "cars-data", _embed(json.dumps(rows, ensure_ascii=False)))
    html = _replace_script(html, "report-meta", _embed(json.dumps(meta, ensure_ascii=False)))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
