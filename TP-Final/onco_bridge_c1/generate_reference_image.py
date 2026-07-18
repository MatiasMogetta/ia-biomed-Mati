"""Genera una referencia sintética Gemini a partir del output de C1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from onco_bridge.reference_generator import SyntheticReferenceGenerator


def suffix_for(mime_type: str) -> str:
    return {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime_type, ".png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera una referencia sintética para C2 con Gemini Image")
    parser.add_argument("c1_output", type=Path, help="JSON producido por run_component1.py")
    parser.add_argument("--output-dir", type=Path, default=Path("generated_references"))
    args = parser.parse_args()

    c1_output = json.loads(args.c1_output.read_text(encoding="utf-8"))
    generated = SyntheticReferenceGenerator().generate(c1_output)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_path = args.output_dir / f"reference_{generated.gt_id}{suffix_for(generated.mime_type)}"
    image_path.write_bytes(generated.data)
    metadata = {
        "gt_id": generated.gt_id,
        "model": generated.model,
        "mime_type": generated.mime_type,
        "image_path": str(image_path),
        "prompt": generated.prompt,
        "limitation": generated.limitation,
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
