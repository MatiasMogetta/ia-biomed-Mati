"""Genera una referencia sintética local con Stable Diffusion para C2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from onco_bridge.local_reference_generator import DEFAULT_LOCAL_MODEL, LocalDiffusionReferenceGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera una referencia C2 local con Stable Diffusion")
    parser.add_argument("c1_output", type=Path, help="JSON producido por run_component1.py")
    parser.add_argument("--output-dir", type=Path, default=Path("generated_references"))
    parser.add_argument("--model-id", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260718)
    args = parser.parse_args()

    c1_output = json.loads(args.c1_output.read_text(encoding="utf-8"))
    generated = LocalDiffusionReferenceGenerator(args.model_id).generate(
        c1_output, device=args.device, steps=args.steps, seed=args.seed
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_path = args.output_dir / f"local_reference_{generated.gt_id}.png"
    image_path.write_bytes(generated.data)
    metadata = {
        "gt_id": generated.gt_id,
        "model": generated.model,
        "image_path": str(image_path),
        "prompt": generated.prompt,
        "limitation": generated.limitation,
    }
    (args.output_dir / "metadata_local.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
