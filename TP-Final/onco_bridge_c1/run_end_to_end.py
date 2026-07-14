"""Ejecuta C1 y C2 de forma secuencial sobre un input clínico y una imagen."""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path

from onco_bridge import ClinicalPipeline, RadiologyAssistant


ROOT = Path(__file__).resolve().parent.parent
GT_DIRECTORY = ROOT / "dataset_clinical_only" / "dataset" / "oncology_ground_truth_base"
DEFAULT_CONFIG = Path(__file__).resolve().parent / "best_hyperparameters.json"

parser = argparse.ArgumentParser(description="OncoBridge AI - Flujo C1 → C2")
parser.add_argument("input", type=Path, help="input.json clínico para C1")
parser.add_argument("image", type=Path, help="Estudio de imagen PNG, JPG o WEBP para C2")
parser.add_argument("--modality", required=True, help="Ej.: mammography, CT, MRI, ultrasound")
parser.add_argument("--view", default="no especificada")
parser.add_argument("--date", dest="acquisition_date", default="no informada")
parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
parser.add_argument("--output", type=Path, default=Path("end_to_end_output.json"))
args = parser.parse_args()

config = {}
if args.config.exists():
    config_payload = json.loads(args.config.read_text(encoding="utf-8"))
    config = config_payload.get("best_config", config_payload)
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
)
result = {"component_1_output": c1_output, "component_2_output": c2_output}
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
