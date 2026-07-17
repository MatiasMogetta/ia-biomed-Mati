"""Pipeline explicable y local para el Componente 1.

No entrega diagnósticos autónomos: prioriza hipótesis del ground truth provisto
y prepara una recomendación para que sea revisada por el profesional.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .semantic import SemanticRetriever


STOPWORDS = {"de", "la", "el", "en", "con", "sin", "y", "a", "o", "un", "una", "del", "por", "para", "que", "se", "es", "al"}
SYNONYMS = {
    "cancer": "cancer", "tumor": "masa", "lump": "masa",
    "lung": "pulmon", "pulmonary": "pulmon", "colon": "colon", "colorectal": "colon",
    "liver": "higado", "pancreatic": "pancreas", "thyroid": "tiroides",
    "kidney": "rinon", "renal": "rinon", "gastric": "estomago", "stomach": "estomago",
    "adrenal": "suprarrenal", "biliary": "biliar", "family": "familiar",
    "palpable": "palpable", "computed": "tomografia", "tomography": "tomografia",
}
ORGAN_TERMS = {
    "pulmon": {"pulmon", "lung", "torax", "tos", "disnea", "hemoptisis"},
    "colon": {"colon", "rectal", "intestinal", "heces", "diverticul"},
    "intestino": {"colon", "rectal", "intestinal", "heces"},
    "tiroides": {"tiroid", "cuello"}, "linfoide": {"linf", "ganglio", "adenopatia"},
    "higado": {"higado", "hepatic", "hepat", "afp", "biliar", "colangio", "ictericia"},
    "pancreas": {"pancreas", "pancreat", "ictericia", "diabetes"},
    "rinon": {"rinon", "renal", "hematuria", "flanco", "orina", "bosniak"},
    "estomago": {"estomago", "gastric", "epigastr", "saciedad", "melena"},
    "suprarrenal": {"suprarrenal", "adrenal", "cortisol", "aldosterona", "metanefrina"},
}
URGENCY_WEIGHT = {"alta": 1.0, "media": 0.60, "baja": 0.30}
SEMANTIC_RETRIEVER_CACHE: dict[tuple[str, str], SemanticRetriever] = {}


def normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return " ".join(SYNONYMS.get(token, token) for token in text.split())


def tokens(value: Any) -> set[str]:
    return {t for t in normalise(value).split() if len(t) > 2 and t not in STOPWORDS}


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(flatten(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(flatten(v) for v in value)
    return str(value)


def overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / max(1, len(a))


@dataclass
class Candidate:
    entry: dict[str, Any]
    retrieval_score: float
    evidence_score: float
    probability: float
    evidence: list[str]


class ClinicalPipeline:
    """RAG léxico con una segunda etapa de scoring clínico determinístico."""

    def __init__(
        self,
        gt_directory: str | Path,
        top_k: int = 5,
        context_k: int = 3,
        scoring_weights: tuple[float, float, float, float, float, float] | None = None,
        raw_weight: float = 0.55,
        referral_threshold: float = 0.42,
        benign_no_referral_threshold: float = 0.45,
        min_match_probability: float = 0.32,
        semantic_weight: float = 0.65,
        semantic_model: str = "BAAI/bge-m3",
        embedding_cache_dir: str | Path | None = None,
    ):
        self.gt_directory = Path(gt_directory)
        self.entries = [json.loads(p.read_text(encoding="utf-8")) for p in self.gt_directory.glob("*.json")]
        if not self.entries:
            raise ValueError(f"No se encontraron entradas GT en {self.gt_directory}")
        self.top_k, self.context_k = top_k, context_k
        self.scoring_weights = scoring_weights or (0.25, 0.30, 0.16, 0.14, 0.08, 0.22)
        if len(self.scoring_weights) != 6 or any(weight < 0 for weight in self.scoring_weights):
            raise ValueError("scoring_weights debe contener seis valores no negativos")
        if not 0 <= raw_weight <= 1:
            raise ValueError("raw_weight debe estar entre 0 y 1")
        self.raw_weight = raw_weight
        self.referral_threshold = referral_threshold
        self.benign_no_referral_threshold = benign_no_referral_threshold
        self.min_match_probability = min_match_probability
        if not 0 <= semantic_weight <= 1:
            raise ValueError("semantic_weight debe estar entre 0 y 1")
        self.semantic_weight = semantic_weight
        cache_dir = embedding_cache_dir or self.gt_directory.parent.parent.parent / "onco_bridge_c1" / ".cache"
        if semantic_weight:
            cache_key = (str(self.gt_directory.resolve()), semantic_model)
            if cache_key not in SEMANTIC_RETRIEVER_CACHE:
                SEMANTIC_RETRIEVER_CACHE[cache_key] = SemanticRetriever(self.entries, cache_dir, semantic_model)
            self.semantic_retriever = SEMANTIC_RETRIEVER_CACHE[cache_key]
        else:
            self.semantic_retriever = None
        self.documents = {e["gt_id"]: tokens(flatten(e)) for e in self.entries}

    def _patient_text(self, patient: dict[str, Any]) -> str:
        relevant = {
            "demographics": patient.get("demographics", {}),
            "current_symptoms": patient.get("current_symptoms", []),
            "medical_history": patient.get("medical_history", [])[-6:],
            "current_labs": patient.get("current_labs", {}),
        }
        return flatten(relevant)

    def retrieve(self, patient: dict[str, Any]) -> list[tuple[dict[str, Any], float]]:
        patient_text = self._patient_text(patient)
        query = tokens(patient_text)
        semantic_scores = self.semantic_retriever.score(patient_text) if self.semantic_retriever else {}
        semantic_weight = self.semantic_weight if self.semantic_retriever and self.semantic_retriever.available else 0.0
        scored = []
        for entry in self.entries:
            lexical = overlap(query, self.documents[entry["gt_id"]])
            organ = entry.get("_meta", {}).get("organ", "")
            organ_bonus = 0.18 if query & ORGAN_TERMS.get(organ, set()) else 0.0
            lexical_score = min(1.0, lexical + organ_bonus)
            semantic_score = semantic_scores.get(entry["gt_id"], 0.0)
            hybrid_score = (1 - semantic_weight) * lexical_score + semantic_weight * semantic_score
            scored.append((entry, hybrid_score))
        return sorted(scored, key=lambda item: item[1], reverse=True)[: self.top_k]

    @staticmethod
    def _threshold_satisfied(value: Any, rule: str) -> bool:
        if not isinstance(value, (int, float)):
            return False
        match = re.search(r"([><])\s*([0-9.]+)", rule)
        if not match:
            return False
        operator, threshold = match.group(1), float(match.group(2))
        return value > threshold if operator == ">" else value < threshold

    def _score(self, patient: dict[str, Any], entry: dict[str, Any], retrieval: float) -> Candidate:
        query = tokens(self._patient_text(patient))
        objective, subjective = entry.get("objective_data", {}), entry.get("subjective_data", {})
        evidence: list[str] = []
        symptom_score = overlap(query, tokens(subjective.get("symptoms", [])))
        finding_score = overlap(query, tokens(objective.get("clinical_findings", [])))
        risk_score = overlap(query, tokens(objective.get("risk_factors", [])))
        history_score = overlap(query, tokens(objective.get("prior_imaging_red_flags", [])))
        biomarkers = objective.get("biomarkers", {})
        matched_biomarkers = [name for name, rule in biomarkers.items() if self._threshold_satisfied(patient.get("current_labs", {}).get(name), rule)]
        biomarker_score = len(matched_biomarkers) / max(1, len(biomarkers))
        age = patient.get("demographics", {}).get("age")
        if isinstance(age, (int, float)) and age >= 50 and "edad" in normalise(objective.get("risk_factors", [])):
            risk_score = max(risk_score, 0.35)
            evidence.append(f"edad {age} compatible con factor de riesgo")
        if symptom_score: evidence.append("síntomas compatibles")
        if finding_score: evidence.append("hallazgos clínicos compatibles")
        if risk_score and not evidence: evidence.append("antecedentes/factores de riesgo compatibles")
        if matched_biomarkers: evidence.append("biomarcadores: " + ", ".join(matched_biomarkers))
        rag_score = min(1, retrieval / 0.45)
        scores = (rag_score, symptom_score, finding_score, risk_score, history_score, biomarker_score)
        raw = sum(weight * score for weight, score in zip(self.scoring_weights, scores))
        base = float(entry.get("base_probability", 0.5))
        probability = max(0.01, min(0.99, self.raw_weight * raw + (1 - self.raw_weight) * base))
        return Candidate(entry, retrieval, raw, probability, evidence)

    def _instructions(self, entry: dict[str, Any], patient: dict[str, Any]) -> dict[str, Any]:
        guidance = entry.get("radiologist_guidance", {})
        return {
            "suggested_modalities": guidance.get("modality_priority", [])[:2],
            "views_recommended": guidance.get("views_recommended", []),
            "imaging_location": guidance.get("imaging_location", {}),
            "clinical_context_for_radiologist": f"Paciente {patient.get('patient_id', 'sin ID')}. " + guidance.get("expected_imaging_findings", ""),
            "meddiffusion_reference_prompt": guidance.get("meddiffusion_prompt", ""),
            "meddiffusion_negative_prompt": guidance.get("meddiffusion_negative_prompt", ""),
            "reference_images_note": guidance.get("image_generation_notes", "Imagen de referencia; no usar como diagnóstico."),
        }

    def analyze(self, patient: dict[str, Any]) -> dict[str, Any]:
        retrieved = self.retrieve(patient)
        candidates = [self._score(patient, entry, score) for entry, score in retrieved]
        candidates.sort(key=lambda c: c.probability, reverse=True)
        selected = [c for c in candidates[: self.context_k] if c.probability >= self.min_match_probability and c.evidence]
        if not selected:
            return self._empty_result(patient, len(retrieved))
        primary = selected[0]
        category = primary.entry.get("_meta", {}).get("category", "")
        urgency = primary.entry.get("urgency_level", "baja") if category != "benigna" else "ninguna"
        imaging_probability = max(c.probability * URGENCY_WEIGHT.get(c.entry.get("urgency_level"), 0.3) for c in selected)
        if category == "benigna" and imaging_probability < self.benign_no_referral_threshold:
            recommendation = "NO_DERIVAR"
        elif imaging_probability >= self.referral_threshold:
            recommendation = "DERIVAR_A_IMAGEN"
        else:
            recommendation, urgency = "SEGUIMIENTO_CLINICO", "baja"
        matches = [{
            "gt_id": c.entry["gt_id"], "icd_10": c.entry["icd_10"],
            "icd_10_description": c.entry["icd_10_description"],
            "match_probability": round(c.probability, 3),
            "match_rationale": "; ".join(c.evidence) or "coincidencia parcial recuperada por RAG",
            "radiologist_instructions": self._instructions(c.entry, patient),
        } for c in selected]
        summary = self._summary(patient)
        return {
            "patient_id": patient.get("patient_id"), "clinical_summary": summary,
            "matched_ground_truths": matches,
            "imaging_needed_probability": round(imaging_probability, 3),
            "reasoning": "Hipótesis recuperadas con RAG local y ordenadas por evidencia clínica, factores de riesgo y biomarcadores. Resultado para revisión profesional; no constituye un diagnóstico.",
            "recommendation": recommendation, "urgency": urgency, "conclusive": True,
            "token_usage": self._usage(patient, len(retrieved), len(selected)),
        }

    def _empty_result(self, patient: dict[str, Any], retrieved: int) -> dict[str, Any]:
        return {"patient_id": patient.get("patient_id"), "clinical_summary": self._summary(patient), "matched_ground_truths": [],
                "imaging_needed_probability": 0.04, "reasoning": "No hay evidencia suficiente para sostener una hipótesis del ground truth. Requiere evaluación clínica profesional si persisten los síntomas.",
                "recommendation": "SIN_ELEMENTOS_PARA_EVALUAR", "urgency": "ninguna", "conclusive": False,
                "token_usage": self._usage(patient, retrieved, 0)}

    def _summary(self, patient: dict[str, Any]) -> str:
        d = patient.get("demographics", {})
        symptoms = "; ".join(patient.get("current_symptoms", [])[:3]) or "sin síntomas consignados"
        return f"Paciente de {d.get('age', 'edad no consignada')} años, sexo {d.get('sex', 'no consignado')}. Motivo actual: {symptoms}."

    def _usage(self, patient: dict[str, Any], retrieved: int, included: int) -> dict[str, Any]:
        # Estimación reproducible: esta versión no invoca un LLM externo.
        compact_context = self._patient_text(patient)
        prompt = math.ceil(len(compact_context.split()) * 1.3) + included * 170
        return {"prompt_tokens": prompt, "completion_tokens": 0, "total_tokens": prompt,
                "model": "local-explainable-rag-v1", "retrieved_gt_entries": retrieved, "gt_entries_in_context": included}
