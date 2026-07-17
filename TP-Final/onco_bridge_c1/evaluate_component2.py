"""Evalúa máscaras binarias de C2 cuando se dispone de un dataset radiológico anotado."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def load_mask(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L")) > 0


def safe_div(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Métricas de segmentación para Componente 2")
    parser.add_argument("manifest", type=Path, help="JSON con prediction_mask y ground_truth_mask por caso")
    parser.add_argument("--report", type=Path, default=Path("artifacts/component2_evaluation.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    base = args.manifest.parent
    rows = []
    totals = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for case in manifest.get("cases", []):
        predicted = load_mask(base / case["prediction_mask"])
        expected = load_mask(base / case["ground_truth_mask"])
        if predicted.shape != expected.shape:
            raise ValueError(f"Dimensiones incompatibles en {case['case_id']}: {predicted.shape} vs {expected.shape}")
        tp = int(np.logical_and(predicted, expected).sum())
        fp = int(np.logical_and(predicted, ~expected).sum())
        fn = int(np.logical_and(~predicted, expected).sum())
        tn = int(np.logical_and(~predicted, ~expected).sum())
        for key, value in (("tp", tp), ("fp", fp), ("fn", fn), ("tn", tn)):
            totals[key] += value
        rows.append({
            "case_id": case["case_id"],
            "iou": round(safe_div(tp, tp + fp + fn), 4),
            "sensitivity": round(safe_div(tp, tp + fn), 4),
            "specificity": round(safe_div(tn, tn + fp), 4),
        })

    if not rows:
        raise ValueError("El manifiesto no contiene casos evaluables.")
    report = {
        "cases": len(rows),
        "mean_iou": round(sum(row["iou"] for row in rows) / len(rows), 4),
        "pixel_sensitivity": round(safe_div(totals["tp"], totals["tp"] + totals["fn"]), 4),
        "pixel_specificity": round(safe_div(totals["tn"], totals["tn"] + totals["fp"]), 4),
        "per_case": rows,
        "note": "Requiere máscaras binarias externas; el dataset clínico provisto no incluye imágenes ni anotaciones.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
