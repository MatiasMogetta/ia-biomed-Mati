"""Genera manifiestos reproducibles 70/30 sin copiar ni mover casos originales."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path


from onco_bridge.config import DATASET_ROOT, dataset_fingerprint


INDEX = DATASET_ROOT / "index.json"
OUTPUT = Path(__file__).resolve().parent / "data_splits"
SEED = 20260712
TRAIN_COUNTS = {"TP": 21, "TN": 21, "FP": 11, "FN": 10, "COMPLEX": 14}


def write_manifest(name: str, cases: list[dict]) -> None:
    payload = {
        "split": name,
        "seed": SEED,
        "dataset_fingerprint": dataset_fingerprint(),
        "strategy": "stratified_by_dataset_category",
        "cases": cases,
        "case_ids": [case["case_id"] for case in cases],
        "count": len(cases),
    }
    (OUTPUT / f"{name}_cases.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in index["cases"]:
        groups[case["category"]].append(case)

    train, test = [], []
    for category, group in sorted(groups.items()):
        shuffled = group.copy()
        random.Random(f"{SEED}-{category}").shuffle(shuffled)
        train_count = TRAIN_COUNTS[category]
        train.extend(shuffled[:train_count])
        test.extend(shuffled[train_count:])

    train.sort(key=lambda c: c["case_id"])
    test.sort(key=lambda c: c["case_id"])
    if len(train) != 77 or len(test) != 33 or set(c["case_id"] for c in train) & set(c["case_id"] for c in test):
        raise RuntimeError("Partición inválida")
    OUTPUT.mkdir(exist_ok=True)
    write_manifest("train", train)
    write_manifest("test", test)
    print("Train: 77 casos | Test: 33 casos | seed: 20260712")
    for category in TRAIN_COUNTS:
        print(f"{category}: train={sum(c['category'] == category for c in train)}, test={sum(c['category'] == category for c in test)}")


if __name__ == "__main__":
    main()
