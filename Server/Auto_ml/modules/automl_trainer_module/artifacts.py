"""Persist a training run and load it back for inference."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

log = logging.getLogger("automl_trainer")


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_run(result, out_dir: str | Path) -> Path:
    """Write models, reports and a manifest (with checksums) to ``out_dir``."""
    out = Path(out_dir)
    (out / "models").mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in result.bundle.items() if k != "model"}

    joblib.dump(result.bundle, out / "best_model.joblib")
    for name, model in result.fitted.items():
        joblib.dump({**meta, "algorithm": name, "model": model}, out / "models" / f"{name.lower()}.joblib")

    def dump(obj, fname):
        (out / fname).write_text(json.dumps(obj, indent=2, default=_json_default))

    dump(result.summary, "run_summary.json")
    dump(result.selection, "selection_report.json")
    dump({"leaderboard": result.leaderboard, "baseline": result.baseline, "tuning": result.tuning,
          "eliminated": result.eliminated}, "training_results.json")
    dump(result.test_details, "test_evaluation.json")

    rows = []
    for r in result.leaderboard:
        flat = {k: v for k, v in r.items() if k not in ("params", "test", "members")}
        flat.update({f"test_{k}": v for k, v in r.get("test", {}).items()})
        flat["params"] = json.dumps(r["params"], default=_json_default)
        flat["members"] = ",".join(r.get("members", []))
        rows.append(flat)
    pd.DataFrame(rows).to_csv(out / "leaderboard.csv", index=False)

    manifest = {
        "best_model": result.summary["best_model"], "created_at": result.summary["created_at"],
        "environment": result.summary["environment"],
        "files": {str(p.relative_to(out)): _sha256(p) for p in sorted(out.rglob("*"))
                  if p.is_file() and p.name != "manifest.json"},
    }
    dump(manifest, "manifest.json")
    log.info("Saved run artifacts to %s", out)
    return out


def load_bundle(path: str | Path, verify: bool = True) -> dict:
    """Load best_model.joblib (or a models/<name>.joblib). Verifies the manifest checksum if present."""
    path = Path(path)
    manifest = path.parent / "manifest.json" if path.name == "best_model.joblib" else path.parent.parent / "manifest.json"
    if verify and manifest.exists():
        files = json.loads(manifest.read_text())["files"]
        rel = str(path.relative_to(manifest.parent)) if path.is_relative_to(manifest.parent) else None
        if rel in files and files[rel] != _sha256(path):
            raise ValueError(f"{path} does not match its manifest checksum; file was modified or corrupted.")
    bundle = joblib.load(path)
    if bundle["environment"]["sklearn"] != sklearn.__version__:
        log.warning("Model trained with scikit-learn %s but running %s.",
                    bundle["environment"]["sklearn"], sklearn.__version__)
    return bundle


def predict(bundle: dict, X: pd.DataFrame, proba: bool = False):
    """Predict from preprocessed features (any column order). Classification returns original labels."""
    missing = [c for c in bundle["features"] if c not in X.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")
    X = X[bundle["features"]]
    model = bundle["model"]
    if proba:
        if not hasattr(model, "predict_proba"):
            raise ValueError(f"{bundle['algorithm']} does not provide probabilities.")
        return model.predict_proba(X)
    pred = model.predict(X)
    classes = bundle.get("label_encoder_classes")
    if bundle["task"] == "classification" and classes is not None:
        return np.asarray(classes)[pred.astype(int)]
    return pred
