"""Generación local de referencias educativas con Stable Diffusion."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

DEFAULT_LOCAL_MODEL = "stable-diffusion-v1-5/stable-diffusion-v1-5"
_PIPELINES: dict[tuple[str, str, bool], Any] = {}


@dataclass
class GeneratedReference:
    """Referencia visual sintética, exclusivamente para el PoC educativo."""

    data: bytes
    mime_type: str
    model: str
    gt_id: str
    prompt: str
    limitation: str


class LocalDiffusionReferenceGenerator:
    """Generador local de ilustraciones, destinado exclusivamente a un PoC educativo."""

    def __init__(self, model_id: str = DEFAULT_LOCAL_MODEL) -> None:
        self.model_id = model_id

    @property
    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import diffusers  # noqa: F401
        except ImportError:
            return False
        return True

    @staticmethod
    def _device(requested: str) -> str:
        import torch

        if requested == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "PyTorch no detecta CUDA en este entorno. Instalá una build CUDA de PyTorch en el mismo venv "
                "y verificá con: python -c \"import torch; print(torch.cuda.is_available())\""
            )
        return requested

    def _pipeline(self, device: str) -> Any:
        import torch

        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        low_vram = device == "cuda" and total_vram_gb < 8
        key = (self.model_id, device, low_vram)
        if key in _PIPELINES:
            return _PIPELINES[key]
        from diffusers import StableDiffusionPipeline

        dtype = torch.float16 if device == "cuda" else torch.float32
        pipeline = StableDiffusionPipeline.from_pretrained(
            self.model_id,
            torch_dtype=dtype,
            use_safetensors=True,
        )
        pipeline.enable_attention_slicing()
        pipeline.enable_vae_slicing()
        if low_vram:
            # Mantiene la mayor parte del modelo en RAM y mueve módulos a la GPU por turnos.
            # Es más lento, pero permite el PoC en GPUs de 4-6 GB.
            pipeline.enable_sequential_cpu_offload()
        else:
            pipeline.to(device)
        _PIPELINES[key] = pipeline
        return _PIPELINES[key]

    @staticmethod
    def _build_prompt(component_1_output: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        matches = component_1_output.get("matched_ground_truths", [])
        if not matches:
            raise ValueError("C1 no devolvió hipótesis; no hay referencia visual para generar.")
        match = matches[0]
        instructions = match.get("radiologist_instructions", {})
        modality = ", ".join(instructions.get("suggested_modalities", [])) or "CT o MRI"
        positive = instructions.get("meddiffusion_reference_prompt", "")
        negative = instructions.get("meddiffusion_negative_prompt", "")
        prompt = (
            "Generate exactly one synthetic educational radiology-style reference image. "
            "This is not a patient study, not diagnostic evidence, and must contain no text, labels, "
            "identifiers, watermarks, or annotations. Use grayscale medical-imaging appearance only. "
            f"Suggested modality: {modality}. Expected visual pattern: {positive}. "
            f"Avoid these features: {negative}. "
            "The image is only an illustrative pattern reference for a radiologist."
        )
        return prompt, match

    def generate(
        self,
        component_1_output: dict[str, Any],
        device: str = "auto",
        steps: int = 30,
        seed: int = 20260718,
    ) -> GeneratedReference:
        if not self.available:
            raise RuntimeError("Faltan diffusers y torch. Ejecutá: pip install -r requirements.txt")
        import torch

        prompt, match = self._build_prompt(component_1_output)
        local_device = self._device(device)
        if local_device == "cpu":
            raise RuntimeError(
                "La generación local en CPU es demasiado lenta para la aplicación. Usá una GPU CUDA o Google Colab."
            )
        generator = torch.Generator(device=local_device).manual_seed(seed)
        image = self._pipeline(local_device)(
            prompt=prompt,
            negative_prompt=(
                "text, watermark, letters, patient identifier, color photography, cartoon, illustration labels"
            ),
            num_inference_steps=steps,
            guidance_scale=7.5,
            generator=generator,
            height=512,
            width=512,
        ).images[0]
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return GeneratedReference(
            data=buffer.getvalue(),
            mime_type="image/png",
            model=f"local:{self.model_id}",
            gt_id=match["gt_id"],
            prompt=prompt,
            limitation=(
                "Referencia sintética educativa generada localmente con Stable Diffusion; es un modelo generalista, "
                "no una imagen clínica real ni una representación radiológica validada."
            ),
        )
