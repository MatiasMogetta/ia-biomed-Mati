"""Generación opcional de referencias sintéticas para C2 mediante Gemini Image."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


load_dotenv()


@dataclass
class GeneratedReference:
    data: bytes
    mime_type: str
    model: str
    gt_id: str
    prompt: str
    limitation: str


class SyntheticReferenceGenerator:
    """Crea una ilustración radiológica sintética, nunca un estudio clínico real."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _primary_match(component_1_output: dict[str, Any]) -> dict[str, Any]:
        matches = component_1_output.get("matched_ground_truths", [])
        if not matches:
            raise ValueError("C1 no devolvió hipótesis; no hay referencia visual para generar.")
        return matches[0]

    def build_prompt(self, component_1_output: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        match = self._primary_match(component_1_output)
        instructions = match.get("radiologist_instructions", {})
        modality = ", ".join(instructions.get("suggested_modalities", [])) or "CT o MRI"
        positive = instructions.get("meddiffusion_reference_prompt", "")
        negative = instructions.get("meddiffusion_negative_prompt", "")
        prompt = (
            "Generate exactly one synthetic educational radiology-style reference image. "
            "This is not a patient study, not diagnostic evidence, and must contain no text, labels, "
            "identifiers, watermarks, or annotations. Use grayscale medical-imaging appearance only. "
            f"Suggested modality: {modality}. "
            f"Expected visual pattern: {positive}. "
            f"Avoid these features: {negative}. "
            "The image is only an illustrative pattern reference for a radiologist."
        )
        return prompt, match

    @staticmethod
    def _image_part(response: Any) -> tuple[bytes, str] | None:
        candidates = getattr(response, "candidates", None) or []
        parts = list(getattr(response, "parts", None) or [])
        for candidate in candidates:
            parts.extend(getattr(getattr(candidate, "content", None), "parts", None) or [])
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return bytes(inline.data), getattr(inline, "mime_type", None) or "image/png"
        return None

    def generate(self, component_1_output: dict[str, Any]) -> GeneratedReference:
        if not self.available:
            raise RuntimeError("No hay GEMINI_API_KEY configurada para generar una referencia sintética.")
        from google import genai
        from google.genai import types

        prompt, match = self.build_prompt(component_1_output)
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        image_part = self._image_part(response)
        if not image_part:
            raise RuntimeError(
                "El modelo no devolvió una imagen. Verificá que GEMINI_IMAGE_MODEL esté habilitado para tu API key."
            )
        data, mime_type = image_part
        return GeneratedReference(
            data=data,
            mime_type=mime_type,
            model=self.model,
            gt_id=match["gt_id"],
            prompt=prompt,
            limitation=(
                "Imagen sintética educativa generada por un modelo generalista; no es un estudio del paciente "
                "ni una referencia radiológica validada."
            ),
        )
