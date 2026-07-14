"""Optimiza pesos explicables de C1 usando solo el manifiesto de entrenamiento.

El conjunto de test no se lee en este script. Debe ejecutarse una sola vez al
final para estimar la generalización de la configuración elegida.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import optuna

from onco_bridge import ClinicalPipeline


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset_clinical_only" / "dataset"
OUTPUT = Path(__file__).resolve().parent


def load_cases(manifest_path: Path) -> list[tuple[dict, dict]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("split") != "train":
        raise ValueError("Por seguridad, el optimizador acepta únicamente un manifiesto con split='train'.")
    cases = []
    for case_id in manifest["case_ids"]:
        case_dir = DATASET / "clinical_cases" / case_id
        cases.append((
            json.loads((case_dir / "input.json").read_text(encoding="utf-8")),
            json.loads((case_dir / "expected_output.json").read_text(encoding="utf-8")),
        ))
    return cases


def metrics(config: dict, cases: list[tuple[dict, dict]]) -> dict:
    pipeline = ClinicalPipeline(DATASET / "oncology_ground_truth_base", **config)
    gt_hits = decisions = tp = fp = fn = tn = 0
    for patient, expected in cases:
        output = pipeline.analyze(patient)
        ids = {item["gt_id"] for item in output["matched_ground_truths"]}
        gt_hits += bool(ids & set(expected["correct_gt_ids"]))
        decisions += output["recommendation"] == expected["specialist_decision"]
        predicted_image = output["recommendation"] == "DERIVAR_A_IMAGEN"
        needed = expected["imaging_needed_ground_truth"]
        if predicted_image and needed: tp += 1
        elif predicted_image: fp += 1
        elif needed: fn += 1
        else: tn += 1
    total = len(cases)
    sensitivity = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "gt_match_accuracy": gt_hits / total,
        "referral_accuracy": decisions / total,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimización de hiperparámetros de OncoBridge C1")
    parser.add_argument("--trials", type=int, default=150, help="Cantidad de configuraciones a evaluar")
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--min-sensitivity", type=float, default=0.80)
    parser.add_argument("--manifest", type=Path, default=OUTPUT / "data_splits" / "train_cases.json")
    args = parser.parse_args()
    cases = load_cases(args.manifest)
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        # Se normalizan para que los seis pesos de evidencia sumen exactamente 1.
        unnormalised = [trial.suggest_float(name, 0.05, 0.45) for name in (
            "w_rag", "w_symptoms", "w_findings", "w_risk", "w_history", "w_biomarkers"
        )]
        total = sum(unnormalised)
        config = {
            "scoring_weights": tuple(round(weight / total, 6) for weight in unnormalised),
            "raw_weight": trial.suggest_float("raw_weight", 0.45, 0.85),
            "referral_threshold": trial.suggest_float("referral_threshold", 0.35, 0.75),
            "benign_no_referral_threshold": trial.suggest_float("benign_no_referral_threshold", 0.30, 0.75),
            "min_match_probability": trial.suggest_float("min_match_probability", 0.20, 0.50),
            "semantic_weight": trial.suggest_float("semantic_weight", 0.30, 0.85),
        }
        result = metrics(config, cases)
        # Prioridad clínica: no se acepta una configuración con sensibilidad insuficiente.
        score = (
            (result["sensitivity"] + result["specificity"] + result["gt_match_accuracy"]) / 3
        )
        if result["sensitivity"] < args.min_sensitivity:
            score -= 2.0 * (args.min_sensitivity - result["sensitivity"])
        trial.set_user_attr("config", config)
        trial.set_user_attr("metrics", result)
        return score

    sampler = optuna.samplers.TPESampler(seed=args.seed)
    study = optuna.create_study(direction="maximize", sampler=sampler, study_name="oncobridge_c1_train")
    study.optimize(objective, n_trials=args.trials)
    best = study.best_trial
    payload = {
        "dataset_split": "train", "case_count": len(cases), "seed": args.seed,
        "trials": args.trials, "minimum_sensitivity": args.min_sensitivity,
        "objective": "(sensitivity + specificity + gt_match_accuracy) / 3",
        "best_objective": best.value, "best_config": best.user_attrs["config"],
        "train_metrics": best.user_attrs["metrics"],
        "warning": "No usar estos resultados como métrica final. Evaluar una única vez con test_cases.json.",
    }
    (OUTPUT / "best_hyperparameters.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUTPUT / "optimization_trials.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["trial", "objective", "sensitivity", "specificity", "gt_match_accuracy", "referral_accuracy", "config"])
        writer.writeheader()
        for trial in study.trials:
            if trial.value is not None:
                trial_metrics = trial.user_attrs["metrics"]
                writer.writerow({"trial": trial.number, "objective": trial.value, **{key: trial_metrics[key] for key in ("sensitivity", "specificity", "gt_match_accuracy", "referral_accuracy")}, "config": json.dumps(trial.user_attrs["config"])})
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
