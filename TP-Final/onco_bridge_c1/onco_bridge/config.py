"""Rutas y carga segura de configuración para la versión actual del proyecto."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "onco_bridge_c1"
DATASET_ROOT = PROJECT_ROOT / "dataset_clinical_only" / "dataset"
GT_DIRECTORY = DATASET_ROOT / "oncology_ground_truth_base"
CASES_DIRECTORY = DATASET_ROOT / "clinical_cases"
ARTIFACTS_DIRECTORY = APP_ROOT / "artifacts"
DEFAULT_CONFIG_PATH = ARTIFACTS_DIRECTORY / "best_hyperparameters.json"


def dataset_fingerprint() -> str:
    """Identifica el contenido GT para impedir reutilizar pesos de otra versión."""
    digest = hashlib.sha256()
    for path in sorted(GT_DIRECTORY.glob("*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def load_pipeline_config(path: str | Path | None) -> dict[str, Any]:
    """Carga pesos y verifica que hayan sido optimizados con el dataset vigente."""
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        return {}
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    recorded = payload.get("dataset_fingerprint")
    current = dataset_fingerprint()
    if recorded != current:
        raise ValueError(
            f"La configuración {config_path} no corresponde al dataset actualizado. "
            "Ejecutá optimize_hyperparameters.py para regenerarla."
        )
    return payload.get("best_config", payload)


def ensure_semantic_ready(pipeline: Any, operation: str = "La ejecución") -> None:
    """Impide presentar un fallback léxico como si fuera el RAG híbrido configurado."""
    if getattr(pipeline, "semantic_weight", 0) <= 0:
        return
    retriever = getattr(pipeline, "semantic_retriever", None)
    if retriever is not None and retriever.available:
        return
    reason = getattr(retriever, "reason_unavailable", "modelo semántico no disponible")
    raise RuntimeError(
        f"{operation} requiere el RAG híbrido BGE-M3 y no permite fallback léxico. "
        f"Detalle: {reason}"
    )
