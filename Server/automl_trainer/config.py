"""Run configuration. Load from a YAML/JSON file or build in code."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class TrainingConfig:
    # --- problem ---------------------------------------------------------
    task: str = "auto"                   # "auto" | "classification" | "regression"
    primary_metric: str | None = None    # clf: accuracy|balanced_accuracy|f1|precision|recall|roc_auc
                                         # reg: r2|rmse|mae  (default accuracy / r2)
    # --- validation ------------------------------------------------------
    cv_splits: int = 5
    cv_repeats: int = 1                  # >1 = repeated CV (more stable, slower)
    random_state: int = 42
    n_jobs: int = -1
    # --- candidate shortlist ---------------------------------------------
    max_candidates: int = 10
    exclude: tuple[str, ...] = ()        # never consider these models
    include_only: tuple[str, ...] = ()   # if set, consider only these models
    rules_path: str | None = None        # custom selection rules (YAML); default: packaged rules.yaml
    # --- efficiency (successive halving) ---------------------------------
    screening_max_rows: int = 5_000      # rung 0 subsamples the training set above this size
    screening_folds: int = 3             # folds for the cheap rung (only when subsampling)
    keep_fraction: float = 0.5           # fraction of models surviving each rung
    keep_min: int = 3                    # never prune below this many models
    time_budget_s: float | None = None   # soft budget, checked between models
    # --- tuning ----------------------------------------------------------
    tune: bool = False
    tune_top_n: int = 3
    tune_iterations: int = 30
    # --- ensembling ------------------------------------------------------
    ensemble: bool = True
    ensemble_top_k: int = 3
    ensemble_min_gain: float = 0.005     # ensemble must beat the best single model by this much
    # --- output ----------------------------------------------------------
    refit_on_all: bool = False           # also refit the winner on train+test for deployment
    overfit_gap_warn: float = 0.10       # train-vs-CV gap that raises a warning

    def __post_init__(self):
        self.exclude, self.include_only = tuple(self.exclude), tuple(self.include_only)
        if self.task not in ("auto", "classification", "regression"):
            raise ValueError(f"task must be auto|classification|regression, got {self.task!r}")
        if self.cv_splits < 2:
            raise ValueError("cv_splits must be >= 2")
        if not 0 < self.keep_fraction <= 1:
            raise ValueError("keep_fraction must be in (0, 1]")
        if self.max_candidates < 1 or self.keep_min < 1 or self.tune_top_n < 0:
            raise ValueError("max_candidates, keep_min must be >= 1 and tune_top_n >= 0")

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingConfig":
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"Unknown config keys: {sorted(unknown)}")
        return cls(**d)

    @classmethod
    def from_file(cls, path: str | Path) -> "TrainingConfig":
        p = Path(path)
        text = p.read_text()
        if p.suffix.lower() in (".yaml", ".yml"):
            import yaml
            return cls.from_dict(yaml.safe_load(text) or {})
        return cls.from_dict(json.loads(text))

    def to_dict(self) -> dict:
        return asdict(self)
