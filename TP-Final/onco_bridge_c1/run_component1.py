"""Ejecuta el Componente 1 sobre un input JSON."""
import argparse
import json
from pathlib import Path

from onco_bridge import ClinicalPipeline

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GT = ROOT / "dataset_clinical_only" / "dataset" / "oncology_ground_truth_base"

parser = argparse.ArgumentParser(description="OncoBridge AI - Componente 1")
parser.add_argument("input", type=Path, help="Ruta a input.json del paciente")
parser.add_argument("--output", type=Path, help="Archivo donde guardar la salida JSON")
parser.add_argument("--top-k", type=int, default=5)
parser.add_argument("--config", type=Path, help="best_hyperparameters.json generado por el optimizador")
args = parser.parse_args()

patient = json.loads(args.input.read_text(encoding="utf-8"))
config = {}
if args.config:
    payload = json.loads(args.config.read_text(encoding="utf-8"))
    config = payload.get("best_config", payload)
result = ClinicalPipeline(DEFAULT_GT, top_k=args.top_k, **config).analyze(patient)
serialized = json.dumps(result, ensure_ascii=False, indent=2)
if args.output:
    args.output.write_text(serialized + "\n", encoding="utf-8")
else:
    print(serialized)
