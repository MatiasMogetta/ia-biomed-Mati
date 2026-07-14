"""Ejecuta el Componente 2 desde consola con un output de C1 y una imagen."""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path

from onco_bridge.component2 import RadiologyAssistant


parser = argparse.ArgumentParser(description="OncoBridge AI - Componente 2")
parser.add_argument("c1_output", type=Path, help="JSON producido por el Componente 1")
parser.add_argument("image", type=Path, help="Imagen PNG, JPG o WEBP del estudio")
parser.add_argument("--modality", required=True, help="Ej.: mammography, CT, MRI, ultrasound")
parser.add_argument("--view", default="no especificada")
parser.add_argument("--date", dest="acquisition_date", default="no informada")
parser.add_argument("--output", type=Path, default=Path("component2_output.json"))
args = parser.parse_args()

c1_output = json.loads(args.c1_output.read_text(encoding="utf-8"))
mime_type = mimetypes.guess_type(args.image.name)[0] or "image/png"
result = RadiologyAssistant().analyze(
    c1_output,
    args.image.read_bytes(),
    mime_type,
    args.modality,
    args.view,
    args.acquisition_date,
)
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
