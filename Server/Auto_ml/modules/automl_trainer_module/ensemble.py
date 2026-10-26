"""Optional soft-voting ensemble of the strongest, most diverse models."""
from __future__ import annotations

from sklearn.ensemble import VotingClassifier, VotingRegressor

from .registry import ModelSpec


def pick_members(ranked_names: list[str], specs: dict[str, ModelSpec], estimators: dict, task: str,
                 top_k: int) -> list[str]:
    """Walk the ranking, preferring one model per family first (diversity), then fill by rank."""
    usable = [n for n in ranked_names
              if task == "regression" or hasattr(estimators[n], "predict_proba")]  # soft voting needs probabilities
    chosen, families = [], set()
    for n in usable:
        if specs[n].family not in families and len(chosen) < top_k:
            chosen.append(n)
            families.add(specs[n].family)
    for n in usable:
        if len(chosen) >= top_k:
            break
        if n not in chosen:
            chosen.append(n)
    return chosen


def build_ensemble(task: str, members: list[str], estimators: dict, n_jobs: int = 1):
    named = [(n, estimators[n]) for n in members]
    if task == "regression":
        return VotingRegressor(named, n_jobs=n_jobs)
    return VotingClassifier(named, voting="soft", n_jobs=n_jobs)
