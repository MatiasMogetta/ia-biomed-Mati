"""Ejecuta C1 y C2 de forma secuencial sobre un input clínico y una imagen."""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path

from onco_bridge import ClinicalPipeline, RadiologyAssistant
from onco_bridge.config import DEFAULT_CONFIG_PATH, GT_DIRECTORY, load_pipeline_config


parser = argparse.ArgumentParser(description="OncoBridge AI - Flujo C1 -> C2")
parser.add_argument("input", type=Path, help="input.json clínico para C1")
parser.add_argument("image", type=Path, help="Estudio de imagen PNG, JPG o WEBP para C2")
parser.add_argument("--modality", required=True, help="Ej.: chest_CT, abdominal_CT, abdominal_MRI")
parser.add_argument("--view", default="no especificada")
parser.add_argument("--date", dest="acquisition_date", default="no informada")
parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
parser.add_argument("--output", type=Path, default=Path("end_to_end_output.json"))
parser.add_argument("--reference-image", type=Path, action="append", default=[], help="Referencia sintética MedDiffusion; se puede repetir")
args = parser.parse_args()

config = load_pipeline_config(args.config)
patient = json.loads(args.input.read_text(encoding="utf-8"))
c1_output = ClinicalPipeline(GT_DIRECTORY, **config).analyze(patient)
mime_type = mimetypes.guess_type(args.image.name)[0] or "image/png"
c2_output = RadiologyAssistant().analyze(
    c1_output,
    args.image.read_bytes(),
    mime_type,
    args.modality,
    args.view,
    args.acquisition_date,
    [(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png") for path in args.reference_image],
)
result = {"component_1_output": c1_output, "component_2_output": c2_output}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
