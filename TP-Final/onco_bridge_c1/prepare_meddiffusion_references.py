"""Exporta los prompts de C1 como manifiesto reproducible para 3D MedDiffusion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara prompts y nombres de archivo para referencias 3D MedDiffusion"
    )
    parser.add_argument("c1_output", type=Path, help="JSON generado por run_component1.py")
    parser.add_argument("--output-dir", type=Path, default=Path("meddiffusion_references"))
    args = parser.parse_args()

    c1_output = json.loads(args.c1_output.read_text(encoding="utf-8"))
    references = []
    for rank, match in enumerate(c1_output.get("matched_ground_truths", []), start=1):
        instructions = match.get("radiologist_instructions", {})
        references.append({
            "rank": rank,
            "gt_id": match["gt_id"],
            "icd_10_description": match.get("icd_10_description", ""),
            "match_probability": match.get("match_probability"),
            "suggested_modalities": instructions.get("suggested_modalities", []),
            "prompt": instructions.get("meddiffusion_reference_prompt", ""),
            "negative_prompt": instructions.get("meddiffusion_negative_prompt", ""),
            "generation_notes": instructions.get("reference_images_note", ""),
            "expected_image_filename": f"{rank:02d}_{match['gt_id']}.png",
            "status": "pending_generation",
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "patient_id": c1_output.get("patient_id"),
        "generator": "3D MedDiffusion (ejecución externa)",
        "warning": "Imágenes sintéticas de referencia; no pertenecen al paciente ni constituyen diagnóstico.",
        "references": references,
    }
    output = args.output_dir / "manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
