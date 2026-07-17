"""Ejecuta el Componente 1 sobre un input JSON."""
import argparse
import json
from pathlib import Path

from onco_bridge import ClinicalPipeline
from onco_bridge.config import DEFAULT_CONFIG_PATH, GT_DIRECTORY, load_pipeline_config

parser = argparse.ArgumentParser(description="OncoBridge AI - Componente 1")
parser.add_argument("input", type=Path, help="Ruta a input.json del paciente")
parser.add_argument("--output", type=Path, help="Archivo donde guardar la salida JSON")
parser.add_argument("--top-k", type=int, default=5)
parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Configuración generada por el optimizador")
args = parser.parse_args()

patient = json.loads(args.input.read_text(encoding="utf-8"))
config = load_pipeline_config(args.config)
result = ClinicalPipeline(GT_DIRECTORY, top_k=args.top_k, **config).analyze(patient)
serialized = json.dumps(result, ensure_ascii=False, indent=2)
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized + "\n", encoding="utf-8")
else:
    print(serialized)
