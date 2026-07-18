"""Ejecuta C1 y C2: análisis clínico y guía visual sintética local."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from onco_bridge import ClinicalPipeline
from onco_bridge.config import DEFAULT_CONFIG_PATH, GT_DIRECTORY, load_pipeline_config
from onco_bridge.local_reference_generator import LocalDiffusionReferenceGenerator


parser = argparse.ArgumentParser(description="OncoBridge AI - Flujo C1 -> C2")
parser.add_argument("input", type=Path, help="input.json clínico para C1")
parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
parser.add_argument("--output", type=Path, default=Path("end_to_end_output.json"))
parser.add_argument("--reference-output", type=Path, help="Ruta del PNG sintético generado; por defecto queda junto al JSON.")
parser.add_argument("--reference-device", choices=["auto", "cuda", "cpu"], default="auto")
parser.add_argument("--reference-steps", type=int, default=20, help="Pasos de difusión de la referencia local.")
parser.add_argument("--reference-seed", type=int, default=20260718)
args = parser.parse_args()

config = load_pipeline_config(args.config)
patient = json.loads(args.input.read_text(encoding="utf-8"))
c1_output = ClinicalPipeline(GT_DIRECTORY, **config).analyze(patient)
args.output.parent.mkdir(parents=True, exist_ok=True)
generated = LocalDiffusionReferenceGenerator().generate(
    c1_output, device=args.reference_device, steps=args.reference_steps, seed=args.reference_seed
)
reference_output = args.reference_output or args.output.parent / f"{args.output.stem}_radiology_reference.png"
reference_output.parent.mkdir(parents=True, exist_ok=True)
reference_output.write_bytes(generated.data)
generated_reference = {
    "image_path": str(reference_output), "mime_type": generated.mime_type, "model": generated.model,
    "gt_id": generated.gt_id, "prompt": generated.prompt, "limitation": generated.limitation,
}
c2_output = {
    "status": "reference_generated", "mode": "prospective_visual_guidance",
    "message": "Se generó una referencia visual sintética basada en la hipótesis principal de C1.",
    "reference_image_path": generated_reference["image_path"], "limitation": generated_reference["limitation"],
}

result = {
    "component_1_output": c1_output,
    "component_2_output": c2_output,
    "generated_radiology_reference": generated_reference,
}
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
