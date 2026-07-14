"""Recuperación semántica local con embeddings y caché de la base GT."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def semantic_document(entry: dict[str, Any]) -> str:
    """Representación clínica compacta; excluye prompts de generación de imágenes."""
    objective = entry.get("objective_data", {})
    subjective = entry.get("subjective_data", {})
    return " ".join([
        entry.get("icd_10_description", ""),
        " ".join(subjective.get("symptoms", [])),
        " ".join(subjective.get("patient_reported_concerns", [])),
        subjective.get("onset_pattern", ""),
        " ".join(objective.get("clinical_findings", [])),
        " ".join(objective.get("risk_factors", [])),
        " ".join(objective.get("prior_imaging_red_flags", [])),
        " ".join(f"{key} {value}" for key, value in objective.get("biomarkers", {}).items()),
        entry.get("notes", ""),
        entry.get("_meta", {}).get("organ", ""),
    ])


class SemanticRetriever:
    """Codifica GT una vez y devuelve similitudes coseno normalizadas a [0, 1]."""

    def __init__(self, entries: list[dict[str, Any]], cache_dir: str | Path, model_name: str = "BAAI/bge-m3"):
        self.entries = entries
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.available = False
        self.reason_unavailable = ""
        self.embeddings = None
        self.model = None
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self.reason_unavailable = "Falta sentence-transformers. Ejecutar: pip install -r requirements.txt"
            return
        self.np = np
        try:
            self.model = SentenceTransformer(model_name)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            fingerprint = hashlib.sha256(
                (model_name + "|" + "|".join(entry["gt_id"] + semantic_document(entry) for entry in entries)).encode("utf-8")
            ).hexdigest()[:16]
            cache_file = self.cache_dir / f"gt_embeddings_{fingerprint}.npy"
            if cache_file.exists():
                self.embeddings = np.load(cache_file)
            else:
                texts = [semantic_document(entry) for entry in entries]
                self.embeddings = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
                np.save(cache_file, self.embeddings)
            self.available = True
        except Exception as error:  # descarga inicial, falta de red o incompatibilidad
            self.reason_unavailable = f"No se pudo cargar {model_name}: {error}"

    def score(self, query: str) -> dict[str, float]:
        if not self.available:
            return {}
        query_embedding = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)[0]
        similarities = self.embeddings @ query_embedding
        # La similitud coseno de embeddings normalizados puede ser negativa; se limita a [0, 1].
        return {entry["gt_id"]: float(max(0.0, min(1.0, score))) for entry, score in zip(self.entries, similarities)}
