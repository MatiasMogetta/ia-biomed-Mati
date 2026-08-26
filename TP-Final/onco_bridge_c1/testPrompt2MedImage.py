"""Prueba técnica aislada de Prompt2MedImage.

Editá IMAGE_PROMPT y NEGATIVE_PROMPT antes de ejecutar. Este script no modifica
el Componente 2 ni la configuración por defecto de OncoBridge AI.

Ejecutar desde la raíz del proyecto:
    python onco_bridge_c1\testPrompt2MedImage.py
"""
from __future__ import annotations

import json
from pathlib import Path


# --- Parámetros editables de la prueba --------------------------------------
MODEL_ID = "Nihirc/Prompt2MedImage"
IMAGE_PROMPT = (
    "Generate a broken hip CT image in the coronal plane."
)
NEGATIVE_PROMPT = (
    "text, letters, labels, watermark, patient identifier, color photography, "
    "cartoon, illustration, multiple panels"
)
SEED = 20260826
STEPS = 60
GUIDANCE_SCALE = 7.5
WIDTH = 512
HEIGHT = 512


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = PROJECT_ROOT / "generated_references" / "prompt2medimage_test"
OUTPUT_IMAGE = OUTPUT_DIRECTORY / "prompt2medimage_example.png"
OUTPUT_METADATA = OUTPUT_DIRECTORY / "prompt2medimage_example.json"


def require_cuda() -> None:
    """Evita una ejecución extremadamente lenta en CPU."""
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("Falta PyTorch. Instalá las dependencias del proyecto.") from error
    if not torch.cuda.is_available():
        raise RuntimeError(
            "Prompt2MedImage se prueba únicamente con GPU CUDA en este script. "
            "Instalá una build CUDA de PyTorch y verificá que torch.cuda.is_available() sea True."
        )


def main() -> None:
    require_cuda()
    import torch
    from diffusers import StableDiffusionPipeline

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"Cargando {MODEL_ID} en GPU CUDA ({vram_gb:.1f} GB de VRAM)...")

    pipeline = StableDiffusionPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        use_safetensors=True,
    )
    pipeline.enable_attention_slicing()
    pipeline.enable_vae_slicing()
    if vram_gb < 8:
        # Reduce el uso de VRAM a costa de velocidad; útil para una prueba aislada.
        pipeline.enable_sequential_cpu_offload()
    else:
        pipeline.to("cuda")

    generator = torch.Generator(device="cuda").manual_seed(SEED)
    image = pipeline(
        prompt=IMAGE_PROMPT,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE_SCALE,
        generator=generator,
        height=HEIGHT,
        width=WIDTH,
    ).images[0]
    image.save(OUTPUT_IMAGE, format="PNG")

    metadata = {
        "model": MODEL_ID,
        "prompt": IMAGE_PROMPT,
        "negative_prompt": NEGATIVE_PROMPT,
        "seed": SEED,
        "steps": STEPS,
        "guidance_scale": GUIDANCE_SCALE,
        "width": WIDTH,
        "height": HEIGHT,
        "output_image": str(OUTPUT_IMAGE),
        "limitation": (
            "Imagen sintética educativa generada para una prueba técnica. "
            "No es un estudio clínico, no representa a un paciente y no constituye evidencia diagnóstica."
        ),
    }
    OUTPUT_METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imagen guardada en: {OUTPUT_IMAGE}")
    print(f"Metadatos guardados en: {OUTPUT_METADATA}")


if __name__ == "__main__":
    main()
