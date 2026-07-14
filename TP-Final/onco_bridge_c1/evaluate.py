"""Evaluación reproducible de los 110 casos clínicos."""
import json
import argparse
from pathlib import Path

from onco_bridge import ClinicalPipeline

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset_clinical_only" / "dataset"
OUTPUT_DIR = Path(__file__).resolve().parent


def safe_div(n, d): return round(n / d, 4) if d else 0.0


def main():
    parser = argparse.ArgumentParser(description="Evalúa el Componente 1 de OncoBridge")
    parser.add_argument("--manifest", type=Path, help="Manifiesto train/test creado por split_dataset.py")
    parser.add_argument("--report", type=Path, help="Ruta opcional para el reporte JSON")
    parser.add_argument("--config", type=Path, help="best_hyperparameters.json generado por el optimizador")
    args = parser.parse_args()
    config = {}
    if args.config:
        payload = json.loads(args.config.read_text(encoding="utf-8"))
        config = payload.get("best_config", payload)
    pipeline = ClinicalPipeline(DATASET / "oncology_ground_truth_base", **config)
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
        predicted_ids = {x["gt_id"] for x in actual["matched_ground_truths"]}
        rows.append({"case_id": case_dir.name, "expected": expected, "actual": actual,
                     "gt_hit": bool(predicted_ids & set(expected["correct_gt_ids"])),
                     "imaging_prediction": actual["recommendation"] == "DERIVAR_A_IMAGEN"})
    n = len(rows)
    gt_hits = sum(r["gt_hit"] for r in rows)
    decision_hits = sum(r["actual"]["recommendation"] == r["expected"]["specialist_decision"] for r in rows)
    tp = sum(r["imaging_prediction"] and r["expected"]["imaging_needed_ground_truth"] for r in rows)
    fp = sum(r["imaging_prediction"] and not r["expected"]["imaging_needed_ground_truth"] for r in rows)
    fn = sum(not r["imaging_prediction"] and r["expected"]["imaging_needed_ground_truth"] for r in rows)
    tn = sum(not r["imaging_prediction"] and not r["expected"]["imaging_needed_ground_truth"] for r in rows)
    brier = sum((r["actual"]["imaging_needed_probability"] - float(r["expected"]["imaging_needed_ground_truth"])) ** 2 for r in rows) / n
    report = {"split": split, "cases": n, "gt_match_accuracy": safe_div(gt_hits, n), "referral_accuracy": safe_div(decision_hits, n),
              "sensitivity": safe_div(tp, tp + fn), "specificity": safe_div(tn, tn + fp), "brier_score": round(brier, 4),
              "mean_estimated_tokens": round(sum(r["actual"]["token_usage"]["total_tokens"] for r in rows) / n, 1),
              "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
              "note": "Métricas sobre datos sintéticos educativos; no reflejan desempeño clínico real."}
    report_path = args.report or OUTPUT_DIR / f"evaluation_report_{split}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
