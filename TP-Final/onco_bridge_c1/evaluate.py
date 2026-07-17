"""Evaluación reproducible de los 110 casos clínicos."""
import json
import argparse
from pathlib import Path

from onco_bridge import ClinicalPipeline
from onco_bridge.config import (
    ARTIFACTS_DIRECTORY,
    DATASET_ROOT,
    DEFAULT_CONFIG_PATH,
    GT_DIRECTORY,
    load_pipeline_config,
)

DATASET = DATASET_ROOT
OUTPUT_DIR = ARTIFACTS_DIRECTORY


def safe_div(n, d): return round(n / d, 4) if d else 0.0


def main():
    parser = argparse.ArgumentParser(description="Evalúa el Componente 1 de OncoBridge")
    parser.add_argument("--manifest", type=Path, help="Manifiesto train/test creado por split_dataset.py")
    parser.add_argument("--report", type=Path, help="Ruta opcional para el reporte JSON")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Configuración generada por el optimizador")
    args = parser.parse_args()
    config = load_pipeline_config(args.config)
    pipeline = ClinicalPipeline(GT_DIRECTORY, **config)
    gt_by_id = {entry["gt_id"]: entry for entry in pipeline.entries}
    rows = []
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        case_dirs = [DATASET / "clinical_cases" / case_id for case_id in manifest["case_ids"]]
        split = manifest["split"]
    else:
        case_dirs = sorted((DATASET / "clinical_cases").glob("case_*"))
        split = "all"
    for case_dir in case_dirs:
        patient = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
        expected = json.loads((case_dir / "expected_output.json").read_text(encoding="utf-8"))
        actual = pipeline.analyze(patient)
        matches = actual["matched_ground_truths"]
        primary = matches[0] if matches else None
        correct_ids = set(expected["correct_gt_ids"])
        primary_correct = bool(primary and primary["gt_id"] in correct_ids)
        expected_prompt = (
            gt_by_id[primary["gt_id"]].get("radiologist_guidance", {}).get("meddiffusion_prompt", "")
            if primary_correct else None
        )
        actual_prompt = primary.get("radiologist_instructions", {}).get("meddiffusion_reference_prompt", "") if primary else ""
        rows.append({"case_id": case_dir.name, "expected": expected, "actual": actual,
                     "gt_hit": primary_correct,
                     "top_probability": float(primary["match_probability"]) if primary else 0.0,
                     "prompt_correct": bool(primary_correct and actual_prompt == expected_prompt),
                     "imaging_prediction": actual["recommendation"] == "DERIVAR_A_IMAGEN"})
    n = len(rows)
    gt_hits = sum(r["gt_hit"] for r in rows)
    decision_hits = sum(r["actual"]["recommendation"] == r["expected"]["specialist_decision"] for r in rows)
    tp = sum(r["imaging_prediction"] and r["expected"]["imaging_needed_ground_truth"] for r in rows)
    fp = sum(r["imaging_prediction"] and not r["expected"]["imaging_needed_ground_truth"] for r in rows)
    fn = sum(not r["imaging_prediction"] and r["expected"]["imaging_needed_ground_truth"] for r in rows)
    tn = sum(not r["imaging_prediction"] and not r["expected"]["imaging_needed_ground_truth"] for r in rows)
    brier = sum((r["actual"]["imaging_needed_probability"] - float(r["expected"]["imaging_needed_ground_truth"])) ** 2 for r in rows) / n
    gt_brier = sum((r["top_probability"] - float(r["gt_hit"])) ** 2 for r in rows) / n
    urgency_hits = sum(r["actual"]["urgency"] == r["expected"]["urgency_ground_truth"] for r in rows)
    conclusive_hits = sum(r["actual"]["conclusive"] == r["expected"]["conclusive_ground_truth"] for r in rows)
    prompt_hits = sum(r["prompt_correct"] for r in rows)
    report = {"split": split, "cases": n, "gt_match_accuracy": safe_div(gt_hits, n), "referral_accuracy": safe_div(decision_hits, n),
              "sensitivity": safe_div(tp, tp + fn), "specificity": safe_div(tn, tn + fp), "brier_score": round(brier, 4),
              "gt_probability_brier_score": round(gt_brier, 4), "urgency_accuracy": safe_div(urgency_hits, n),
              "conclusive_accuracy": safe_div(conclusive_hits, n), "meddiffusion_prompt_accuracy": safe_div(prompt_hits, n),
              "mean_estimated_tokens": round(sum(r["actual"]["token_usage"]["total_tokens"] for r in rows) / n, 1),
              "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
              "note": "Métricas sobre datos sintéticos educativos; no reflejan desempeño clínico real."}
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = args.report or OUTPUT_DIR / f"evaluation_report_{split}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
