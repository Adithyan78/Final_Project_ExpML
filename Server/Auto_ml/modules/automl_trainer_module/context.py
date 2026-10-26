"""Turn the upstream modules' outputs into a flat 'dataset context' used by the selection rules.

Uses all three artifacts when available:
  * dataset_profile.json        -> class balance, target association, outliers, skew, column types
  * feature_provenance.json     -> how each model input was produced (one-hot / scaled / target-encoded)
  * preprocessing_summary.json  -> which features were finally selected

Anything missing falls back to statistics computed from the data itself.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import UpstreamArtifacts


def _provenance_stats(provenance: list | None, columns: list[str]) -> dict:
    """Stats over the features that actually reach the model (provenance lists pre-selection features)."""
    if not provenance:
        return {}
    rows = [p for p in provenance if p["output_feature"] in set(columns)]
    if not rows:
        return {}
    transforms = [p["transformation"] for p in rows]
    sources = sorted({p["source_column"] for p in rows})
    cat_sources = {p["source_column"] for p in rows
                   if any(t in p["transformation"] for t in ("one_hot", "ordinal", "target_encode"))}
    num_sources = {p["source_column"] for p in rows if "scale" in p["transformation"]}
    return {
        "source_columns": sources,
        "n_source_columns": len(sources),
        "onehot_share": float(np.mean(["one_hot" in t for t in transforms])),
        "has_target_encoded": any("target_encode" in t for t in transforms),
        "has_categorical_source": bool(cat_sources),
        "has_numeric_source": bool(num_sources),
    }


def _profile_stats(profile: dict | None, source_columns: list[str] | None) -> dict:
    if not profile:
        return {}
    out: dict = {}
    target = profile.get("target", {})
    if "imbalance_flag" in target:
        out["imbalanced"] = bool(target["imbalance_flag"])
    assoc = profile.get("target_association", {})
    cols = profile.get("columns", {})
    keep = [c for c in (source_columns or list(assoc)) if c in assoc and not cols.get(c, {}).get("id_like")]
    if keep:
        scores = [assoc[c]["score"] for c in keep]
        out["max_target_association"] = float(max(scores))
        out["mean_target_association"] = float(np.mean(scores))
    used = [cols[c] for c in (source_columns or cols) if c in cols]
    out["outlier_heavy"] = any(c.get("outlier_pct", 0) > 10 for c in used)
    out["highly_skewed"] = any(abs(c.get("skew", 0)) > 2 for c in used if c.get("inferred_type") == "numeric")
    return out


def build_context(upstream: UpstreamArtifacts, X: pd.DataFrame, y: pd.Series, task: str) -> dict:
    prov = _provenance_stats(upstream.provenance, list(X.columns))
    prof = _profile_stats(upstream.profile, prov.get("source_columns"))

    binary_share = float(np.mean([X[c].nunique() <= 2 for c in X.columns]))
    multi = [c for c in X.columns if X[c].nunique() > 2]
    max_corr = 0.0
    if len(multi) >= 2:
        corr = X[multi].corr().abs().to_numpy().copy()
        np.fill_diagonal(corr, 0)
        max_corr = float(np.nanmax(corr))

    if task == "classification":
        shares = y.value_counts(normalize=True)
        minority, n_classes = float(shares.min()), int(y.nunique())
        imbalanced = prof.get("imbalanced", minority < 0.15)
    else:
        minority, n_classes, imbalanced = None, 0, False

    n_rows, n_features = len(X), X.shape[1]
    return {
        "task": task,
        "n_rows": n_rows,
        "n_features": n_features,
        "feature_row_ratio": round(n_features / n_rows, 4),
        "n_classes": n_classes,
        "minority_share": None if minority is None else round(minority, 4),
        "imbalanced": bool(imbalanced),
        "binary_share": round(binary_share, 4),
        "onehot_share": round(prov.get("onehot_share", binary_share), 4),
        "has_categorical_source": prov.get("has_categorical_source", binary_share > 0.5),
        "has_numeric_source": prov.get("has_numeric_source", len(multi) > 0),
        "has_target_encoded": prov.get("has_target_encoded", False),
        "n_source_columns": prov.get("n_source_columns", n_features),
        "max_abs_num_corr": round(max_corr, 4),
        "max_target_association": round(prof.get("max_target_association", 0.0), 4),
        "mean_target_association": round(prof.get("mean_target_association", 0.0), 4),
        "outlier_heavy": prof.get("outlier_heavy", False),
        "highly_skewed": prof.get("highly_skewed", False),
        "used_profile": upstream.profile is not None,
        "used_provenance": bool(prov),
    }
