"""Asistente generativo fundamentado exclusivamente en el output de C1."""
from __future__ import annotations

import json
import os
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

load_dotenv()

SYSTEM_INSTRUCTIONS = """
Eres OncoBridge AI, un asistente de apoyo para profesionales de salud.
Responde siempre en español claro, profesional y conciso. Tu única fuente clínica es el
output estructurado del Componente 1 proporcionado en el contexto. No inventes datos, diagnósticos,
guías, dosis ni tratamientos que no aparezcan en el contexto. No reemplazas el juicio
clínico; recuerda que la decisión final corresponde al médico. Si se solicita una segunda
opinión, ofrece un análisis explicativo de la evidencia y las limitaciones del output, no
un diagnóstico independiente. Cuando falte información, dilo explícitamente.
**Output esperado frente a análisis inicial:**
# Hipótesis más probable
- Debajo de este titulo se dirá explicitamente cuál es la patología más probable para este caso, y se justificará porqué es la hipótesis más probable.
# Derivación y Urgencia
- Explica si el paciente debe ser derivado a diagnóstico por imágenes y qué urgencia tiene.
# Otras posibles hipótesis
- Enumera otras posibles hipótesis brevemente

**Output esperado frente a pregunta follow up del profesional:**
Puedes responder libremente a la pregunta del profesional, pero siempre basándote en el output del Componente 1. No inventes información ni hagas recomendaciones que no estén fundamentadas en el output. Si no hay suficiente información para responder, dilo explícitamente.
"""


def local_summary(output: dict[str, Any]) -> str:
    """Resumen legible cuando no hay una API generativa configurada."""
    hypotheses = output.get("matched_ground_truths", [])
    if not output.get("conclusive"):
        return (
            "El análisis no encontró evidencia suficiente para sostener una hipótesis del ground truth. "
            "Se recomienda revisión clínica profesional si los síntomas persisten o cambian."
        )
    lines = [output.get("clinical_summary", "Resumen clínico no disponible.")]
    if hypotheses:
        lines.append("Hipótesis recuperadas: " + "; ".join(
            f"{item['icd_10_description']} ({item['match_probability']:.0%})" for item in hypotheses
        ) + ".")
    recommendation = output.get("recommendation", "SIN_ELEMENTOS_PARA_EVALUAR")
    urgency = output.get("urgency", "ninguna")
    lines.append(f"Recomendación del sistema: {recommendation}. Urgencia: {urgency}.")
    lines.append("Resultado de apoyo; la decisión diagnóstica y terapéutica final corresponde al médico.")
    return " ".join(lines)


class ClinicalAssistant:
    """Cliente opcional de Gemini para la capa conversacional."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def answer(self, c1_output: dict[str, Any], user_question: str | None = None, history: list[dict[str, str]] | None = None) -> str:
        if not self.available:
            if user_question:
                return "No hay un modelo generativo configurado. Configurá GEMINI_API_KEY para habilitar el chat contextual."
            return local_summary(c1_output)
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        context = json.dumps(c1_output, ensure_ascii=False, indent=2)
        conversation = "\n".join(
            f"{message['role'].upper()}: {message['content']}" for message in (history or [])[-6:]
        )
        task = user_question or (
            "Redactá un resumen para el médico: hipótesis principales, evidencia relevante, "
            "recomendación de imágenes, urgencia y limitaciones. No muestres JSON."
        )
        response = client.models.generate_content(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS,
                temperature=0.2,
            ),
            contents=(
                f"OUTPUT VERIFICADO DEL COMPONENTE 1:\n{context}\n\n"
                f"CONVERSACIÓN PREVIA:\n{conversation or 'Sin mensajes previos.'}\n\n"
                f"SOLICITUD DEL MÉDICO:\n{task}"
            ),
        )
        if not response.text:
            return "Gemini no devolvió texto para esta consulta. Revisá la configuración del modelo e intentá nuevamente."
        return response.text
