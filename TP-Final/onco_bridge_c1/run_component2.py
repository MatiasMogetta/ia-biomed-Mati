"""Ejecuta C2: genera una guía visual sintética desde el output de C1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from onco_bridge.local_reference_generator import LocalDiffusionReferenceGenerator


parser = argparse.ArgumentParser(description="OncoBridge AI - Componente 2 (referencia visual local)")
parser.add_argument("c1_output", type=Path, help="JSON producido por el Componente 1")
parser.add_argument("--output-dir", type=Path, default=Path("generated_references"))
parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
parser.add_argument("--steps", type=int, default=30)
parser.add_argument("--seed", type=int, default=20260718)
parser.add_argument("--force", action="store_true", help="Genera la referencia aunque C1 no recomiende derivación")
args = parser.parse_args()

c1_output = json.loads(args.c1_output.read_text(encoding="utf-8"))
args.output_dir.mkdir(parents=True, exist_ok=True)
should_generate = bool(c1_output.get("matched_ground_truths")) and (
    args.force or c1_output.get("recommendation") == "DERIVAR_A_IMAGEN"
)
if should_generate:
    generated = LocalDiffusionReferenceGenerator().generate(
        c1_output, device=args.device, steps=args.steps, seed=args.seed
    )
    image_path = args.output_dir / f"local_reference_{generated.gt_id}.png"
    image_path.write_bytes(generated.data)
    result = {
        "status": "reference_generated", "mode": "prospective_visual_guidance",
        "reference_image_path": str(image_path), "gt_id": generated.gt_id,
        "model": generated.model, "prompt": generated.prompt, "limitation": generated.limitation,
    }
else:
    result = {
        "status": "not_required", "mode": "prospective_visual_guidance",
        "reference_image_path": None, "gt_id": None, "model": None, "prompt": None,
        "limitation": "C2 no generó una referencia porque C1 no recomendó derivación a imágenes.",
    }
(args.output_dir / "component2_output.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2))
