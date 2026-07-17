"""Componente 2: asistencia radiológica basada en C1 y un estudio de imagen."""
from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # C1 puede ejecutarse sin las dependencias opcionales de Gemini.
    def load_dotenv() -> bool:
        return False

load_dotenv()

C2_SYSTEM_INSTRUCTIONS = """Eres el Componente 2 de OncoBridge AI, una herramienta de apoyo
para radiólogos. Recibís el output verificado del Componente 1, una imagen clínica y,
cuando estén disponibles, imágenes sintéticas de referencia generadas con 3D MedDiffusion.
Contrastá las hipótesis y zonas de interés de C1 con lo observable en el estudio del paciente.
Las referencias muestran patrones esperados y nunca son evidencia del caso real.

Respondé ÚNICAMENTE con un objeto JSON válido, sin Markdown ni texto adicional, con este esquema:
{
  "patient_id": "string",
  "segmentation": {"regions_of_interest": [
    {"id": "ROI-01", "location": "string", "size_mm": number|null,
     "shape": "string", "margins": "string", "density": "string"}
  ]},
  "findings": "string",
  "classification": "sospechoso|indeterminado|sin_hallazgos_relevantes|imagen_no_evaluable",
  "confidence": number entre 0 y 1,
  "final_recommendation": "string",
  "next_steps": ["string"]
}

Reglas obligatorias:
- No inventes hallazgos, tamaños ni lateralidad. Si la escala no es visible, usa null en size_mm.
- Si la imagen no permite una lectura válida o su modalidad no es adecuada, indicá imagen_no_evaluable.
- Las ROI son una orientación descriptiva, no una segmentación pixel a pixel ni un diagnóstico confirmado.
- No prescribas tratamientos. La conclusión final corresponde al radiólogo y al equipo tratante.
- Usá las instrucciones de C1 como guía, pero no confirmes una hipótesis si la imagen no la respalda.
"""


def _extract_json(text: str) -> dict[str, Any]:
    """Acepta JSON puro o una respuesta envuelta accidentalmente en un bloque Markdown."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Gemini no devolvió un objeto JSON para el análisis radiológico.")
    return json.loads(cleaned[start:end + 1])


def _normalise_output(payload: dict[str, Any], patient_id: str, model: str, usage: Any) -> dict[str, Any]:
    segmentation = payload.get("segmentation") if isinstance(payload.get("segmentation"), dict) else {}
    regions = segmentation.get("regions_of_interest", [])
    if not isinstance(regions, list):
        regions = []
    normalised_regions = []
    for index, region in enumerate(regions, start=1):
        size = region.get("size_mm")
        normalised_regions.append({
            "id": region.get("id") or f"ROI-{index:02d}",
            "location": str(region.get("location") or "No especificada"),
            "size_mm": size if isinstance(size, (int, float)) else None,
            "shape": str(region.get("shape") or "No especificada"),
            "margins": str(region.get("margins") or "No especificados"),
            "density": str(region.get("density") or "No especificada"),
        })
    confidence = payload.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    allowed_classifications = {"sospechoso", "indeterminado", "sin_hallazgos_relevantes", "imagen_no_evaluable"}
    classification = str(payload.get("classification") or "indeterminado")
    if classification not in allowed_classifications:
        classification = "indeterminado"
    next_steps = payload.get("next_steps", [])
    if not isinstance(next_steps, list):
        next_steps = []
    return {
        "patient_id": payload.get("patient_id") or patient_id,
        "segmentation": {"regions_of_interest": normalised_regions},
        "findings": str(payload.get("findings") or "Sin hallazgos estructurados reportados."),
        "classification": classification,
        "confidence": confidence,
        "final_recommendation": str(payload.get("final_recommendation") or "Revisión por especialista en imágenes."),
        "next_steps": [str(step) for step in next_steps],
        "token_usage": {
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "completion_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
            "model": model,
        },
        "limitations": "ROI descriptivas generadas por IA; no constituyen segmentación pixel a pixel ni informe radiológico definitivo.",
    }


class RadiologyAssistant:
    """Ejecuta C2 con Gemini Vision a partir de C1 y una imagen cargada por el usuario."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def analyze(
        self,
        component_1_output: dict[str, Any],
        image_bytes: bytes,
        mime_type: str,
        modality: str,
        view: str,
        acquisition_date: date | str | None = None,
        reference_images: list[tuple[bytes, str]] | None = None,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("No hay GEMINI_API_KEY configurada para ejecutar el Componente 2.")
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        date_value = acquisition_date.isoformat() if isinstance(acquisition_date, date) else str(acquisition_date or "no informada")
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/png")
        context = {
            "component_1_output": component_1_output,
            "imaging_study": {
                "modality": modality,
                "view": view,
                "acquisition_date": date_value,
            },
        }
        contents: list[Any] = [json.dumps(context, ensure_ascii=False), image_part]
        if reference_images:
            contents.append(
                "Las imágenes siguientes son referencias sintéticas 3D MedDiffusion; "
                "no pertenecen al paciente y solo sirven para contrastar patrones."
            )
            contents.extend(
                types.Part.from_bytes(data=data, mime_type=reference_mime or "image/png")
                for data, reference_mime in reference_images
            )
        response = client.models.generate_content(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=C2_SYSTEM_INSTRUCTIONS,
                temperature=0.1,
                response_mime_type="application/json",
            ),
            contents=contents,
        )
        if not response.text:
            raise RuntimeError("Gemini no devolvió un análisis radiológico.")
        payload = _extract_json(response.text)
        return _normalise_output(payload, component_1_output.get("patient_id", "sin_id"), self.model, getattr(response, "usage_metadata", None))
